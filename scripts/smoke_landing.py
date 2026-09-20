"""Browser + production HTML checks. Requires built frontend served by Nginx.

No credentials, no writes. Run alongside smoke_auth.py for real auth coverage.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base = os.getenv('BASKETVISION_SMOKE_URL', 'http://localhost:5174')
out = Path(__file__).resolve().parents[1] / 'storage' / 'diagnostics' / 'homepage'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context(viewport={'width':1440,'height':1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    response = page.goto(base + '/')
    assert response.status == 200
    assert response.headers['x-robots-tag'] == 'index, follow'
    raw = response.text()
    assert '<h1' in raw and 'La tua partita.' in raw
    assert 'application/ld+json' in raw
    expect(page.locator('h1')).to_have_count(1)
    expect(page.locator('form')).to_have_count(0)
    expect(page.locator('meta[name="robots"]')).to_have_attribute('content','index, follow')
    expect(page.locator('link[rel="canonical"]')).to_have_attribute('href','https://basketvision.it/')
    for field in ['title','description','url','type','site_name']:
        assert page.locator(f'meta[property="og:{field}"]').get_attribute('content')
    assert page.locator('meta[name="description"]').get_attribute('content')
    assert len(json.loads(page.locator('#bv-structured-data').text_content())['@graph']) == 2
    page.screenshot(path=str(out/'desktop.png'),full_page=True)
    for width in [360,390,768]:
        page.set_viewport_size({'width':width,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
        expect(page.get_by_role('link',name='Prova BasketVision').nth(1)).to_be_visible()
        page.screenshot(path=str(out/f'width-{width}.png'),full_page=True)
    # Anchors and keyboard-visible skip link.
    page.goto(base+'/')
    page.keyboard.press('Tab')
    expect(page.get_by_role('link',name='Vai al contenuto')).to_be_focused()
    page.get_by_role('link',name='Scopri come funziona').click()
    assert page.url.endswith('#come-funziona')
    page.get_by_role('link',name='Prova BasketVision').nth(1).click()
    expect(page.get_by_role('heading',name='Accedi',exact=True)).to_be_visible()
    expect(page.locator('meta[name="robots"]')).to_have_attribute('content','noindex, nofollow')
    expect(page.locator('link[rel="canonical"]')).to_have_count(0)
    # Login error, same API contract, no mutation of real users.
    page.route('**/auth/login',lambda r:r.fulfill(status=401,json={'message':'Credenziali non valide.'}))
    page.get_by_label('Email',exact=True).fill('invalid@example.invalid')
    page.get_by_label('Password',exact=True).fill('invalid-password')
    page.get_by_role('button',name='Accedi',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('Credenziali non valide.')
    for route in ['/login','/admin','/dashboard','/profile','/reports/example','/?game=example','/?utm_source=test']:
        response = page.goto(base+route)
        assert response.headers['x-robots-tag']=='noindex, nofollow',route
        assert 'content="noindex, nofollow"' in response.text(),route
        assert 'bv-hero' not in response.text(),route
        expect(page.locator('meta[name="robots"]')).to_have_attribute('content','noindex, nofollow')
        expect(page.get_by_role('heading',name='Accedi',exact=True)).to_be_visible()
    robots = context.request.get(base+'/robots.txt')
    assert robots.status==200 and 'Disallow: /\n' not in robots.text()
    sitemap = context.request.get(base+'/sitemap.xml').text()
    assert sitemap.count('<loc>')==1 and '<loc>https://basketvision.it/</loc>' in sitemap
    assert context.request.get(base+'/assets/missing.js').status==404
    nojs = browser.new_context(java_script_enabled=False)
    static = nojs.new_page()
    static.goto(base+'/')
    expect(static.locator('h1')).to_have_count(1)
    expect(static.get_by_role('link',name='Prova BasketVision').nth(1)).to_be_visible()
    nojs.close()
    assert not errors, errors
    browser.close()
print('PASS: prerender, SEO, private noindex, mobile, navigation, login error and JS errors.')
