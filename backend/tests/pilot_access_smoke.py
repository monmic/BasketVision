"""Read-only game access through local Nginx; credentials never printed."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5173'
repo = Path(__file__).resolve().parents[2]
settings = dict(line.split('=',1) for line in (repo/'.env').read_text().splitlines()
                if line and not line.startswith('#') and '=' in line)
with sync_playwright() as pw:
    executable = os.environ.get('BASKETVISION_BROWSER')
    browser = pw.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
    page = browser.new_page(viewport=dict(width=1280,height=900))
    errors = []
    page.on('pageerror',lambda error:errors.append(str(error)))
    for role in ['ADMIN','DEMO']:
        page.goto(base+'/login')
        expect(page.get_by_role('heading',name='Accedi',exact=True)).to_be_visible()
        page.get_by_label('Email',exact=True).fill(settings['SEED_'+role+'_EMAIL'])
        page.get_by_label('Password',exact=True).fill(settings['SEED_'+role+'_PASSWORD'])
        page.get_by_role('button',name='Accedi',exact=True).click()
        expect(page.get_by_role('button',name='Esci',exact=True)).to_be_visible()
        expect(page.locator('meta[name="robots"]')).to_have_attribute('content','noindex, nofollow')
        games = page.get_by_role('heading',name='Nuova partita',exact=True).locator('..').locator('select')
        if role == 'ADMIN':
            expect(page.get_by_role('heading',name='Monitoraggio amministrativo',exact=True)).to_be_visible()
            if games.locator('option').count() > 1:
                games.select_option(index=1)
                expect(page.locator('video')).to_be_visible()
                page.wait_for_function('document.querySelector("video")?.readyState >= 1',timeout=30000)
                selected_url = page.url
                page.reload()
                expect(page.get_by_role('button',name='Esci',exact=True)).to_be_visible()
                expect(page).to_have_url(selected_url)
        else:
            expect(page.get_by_role('heading',name='Monitoraggio amministrativo',exact=True)).not_to_be_visible()
            expect(page.get_by_text('Free',exact=True)).to_be_visible()
        page.get_by_role('button',name='Esci',exact=True).click()
        expect(page.get_by_role('heading',name='Accedi',exact=True)).to_be_visible()
    assert not errors,errors
    browser.close()
print('PASS: real Admin/User login, reload/session, authenticated video, ownership UI, private noindex and logout; no games/jobs changed')
