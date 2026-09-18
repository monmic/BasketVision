"""Optional local browser smoke test. Requires Playwright and Microsoft Edge.

Reads seed credentials from the ignored .env without printing them.
Does not create, change or delete games or analyses.
"""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parents[1]
settings = dict(line.split("=", 1) for line in (root / ".env").read_text().splitlines()
                if line and not line.startswith("#") and "=" in line)
artifacts = root / "storage" / "backups"
artifacts.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://localhost:5173")
    expect(page.get_by_role("heading", name="Accedi")).to_be_visible()

    def login(role):
        page.get_by_label("Email", exact=True).fill(settings[f"SEED_{role}_EMAIL"])
        page.get_by_label("Password", exact=True).fill(settings[f"SEED_{role}_PASSWORD"])
        page.get_by_role("button", name="Accedi", exact=True).click()
        expect(page.get_by_role("button", name="Esci")).to_be_visible()

    login("ADMIN")
    expect(page.get_by_text("Unlimited — Admin", exact=True)).to_be_visible()
    games = page.locator("section").filter(has=page.get_by_role("heading", name="Nuova partita")).locator("select")
    expect(games.locator("option").nth(1)).to_be_attached()
    games.select_option(index=1)
    page.wait_for_function("document.querySelector('video')?.readyState >= 1", timeout=30000)
    expect(page.get_by_role("heading", name=re.compile("Vision debug"))).to_be_visible(timeout=30000)
    images = page.locator(".debug-gallery img")
    if images.count():
        page.wait_for_function("Array.from(document.querySelectorAll('.debug-gallery img')).every(i => i.complete && i.naturalWidth > 0)")
    page.screenshot(path=str(artifacts / "auth-admin.png"), full_page=True)
    page.reload()
    expect(page.get_by_text("Unlimited — Admin", exact=True)).to_be_visible()
    page.get_by_role("button", name="Esci").click()
    expect(page.get_by_role("heading", name="Accedi")).to_be_visible()
    login("DEMO")
    expect(page.get_by_text("Free", exact=True)).to_be_visible()
    expect(page.get_by_text("Eventi avanzati: 🔒 bloccato dal piano", exact=True)).to_be_visible()
    expect(page.get_by_text("Gestione piani utenti", exact=True)).to_have_count(0)
    games = page.locator("section").filter(has=page.get_by_role("heading", name="Nuova partita")).locator("select")
    expect(games.locator("option")).to_have_count(1)
    page.screenshot(path=str(artifacts / "auth-free.png"), full_page=True)
    page.get_by_role("button", name="Esci").click()
    assert not errors, errors
    browser.close()
print("Browser smoke passed: admin login, legacy game, video, debug images, refresh, logout, Free plan and ownership.")
