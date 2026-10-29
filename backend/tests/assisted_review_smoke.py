"""Browser smoke against a built frontend, with isolated API fixtures (no user data).

Run with Playwright installed: python tests/assisted_review_smoke.py [preview URL]
Set BASKETVISION_BROWSER to an installed Chromium/Edge executable if needed.
"""
import json
import os
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5174"
game = {"id": "game-1", "name": "Smoke Home vs Away", "videoPath": "fixture.mp4",
        "teams": [{"id": "home", "name": "Home", "side": "A"}, {"id": "away", "name": "Away", "side": "B"}]}
session = {"analysisId": "review-1", "gameId": game["id"], "isManualReview": True,
           "status": "Completed", "progress": 100, "createdAtUtc": "2026-10-26T10:00:00Z"}
events = []
opened = False
fail_report = False
posts = 0

def report():
    teams = []
    for team in game["teams"]:
        counted = [e for e in events if e["teamId"] == team["id"] and e["status"] in ("Confirmed", "Corrected")]
        categories = []
        for value in (1, 2, 3):
            attempts = [e for e in counted if e["shotValue"] == value]
            made = sum(e["type"] == "ShotMade" for e in attempts)
            categories.append({"value": value, "made": made, "attempted": len(attempts),
                               "percentage": round(100 * made / len(attempts), 1) if attempts else None})
        teams.append({"teamId": team["id"], "teamName": team["name"], "stats": {},
                      "shooting": {"points": sum(c["value"] * c["made"] for c in categories), "unspecified": 0, "categories": categories}})
    return {"gameId": game["id"], "gameName": game["name"], "teams": teams, "events": events}

def api(route):
    global opened, fail_report, posts
    path = urlparse(route.request.url).path
    method = route.request.method
    status, body = 200, {}
    if path == "/auth/refresh": body = {"accessToken": "isolated-fixture"}
    elif path == "/auth/me":
        body = {"id": "user-1", "email": "fixture@test.local", "roles": ["User"], "plan": "Fixture", "bypass": True,
                "entitlements": {}, "usage": {"analysesStarted": 0, "reservedMinutes": 0, "analyzedMinutes": 0, "storageBytes": 0}}
    elif path == "/api/games": body = [game]
    elif path == "/api/games/game-1": body = game
    elif path == "/api/analysis/active": body = []
    elif path.endswith("/analyses"): body = [session] if opened else []
    elif path.endswith("/review"):
        opened = True
        body = session
    elif path.endswith("/video"):
        route.fulfill(status=204, body=""); return
    elif "/shots" in path:
        body = route.request.post_data_json
        if method == "POST":
            posts += 1
            body["id"] = f"event-{posts}"
            events.append(body)
        else:
            event = next(e for e in events if e["id"] == path.split("/")[-1])
            event.update(body)
            body = event
        body["team"] = next((t["name"] for t in game["teams"] if t["id"] == body["teamId"]), None)
        body["confidence"] = 1
    elif path.endswith("/report"):
        if fail_report: status, body = 503, {"message": "Fixture report unavailable"}
        else: body = report()
    elif path.endswith("/report.csv"):
        route.fulfill(status=200, content_type="text/csv", body="team,points\nHome,0\n"); return
    else: raise AssertionError(f"Unexpected API call: {method} {path}")
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

with sync_playwright() as pw:
    executable = os.environ.get("BASKETVISION_BROWSER")
    browser = pw.chromium.launch(headless=True, **({"executable_path": executable} if executable else {}))
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/auth/**", api)
    page.route("**/api/**", api)
    page.goto(base + "/?game=game-1")
    expect(page.get_by_role("button", name="Avvia analisi CV")).to_be_visible()
    expect(page.get_by_role("button", name="Inizia revisione assistita")).not_to_be_visible()
    page.get_by_text("Strumenti di verifica manuale", exact=True).click()
    page.get_by_role("button", name="Inizia revisione assistita").click()
    page.get_by_text("Verifica e correzione manuale dei tiri", exact=True).click()
    review = page.locator(".shot-review")
    expect(review).to_be_visible()
    expect(page).to_have_url(base + "/?game=game-1&analysis=review-1")
    page.locator("video").evaluate("v => { v.currentTime = 12.345678; }")
    review.get_by_role("button", name="Aggiungi tiro dalla posizione del video").click()
    expect(review.get_by_label("Secondi video")).to_have_value("12.35")
    review.get_by_label("Squadra").select_option("home")
    review.get_by_label("Tipo di tiro").select_option("3")
    review.get_by_role("button", name="Salva tiro").click()
    expect(page.get_by_role("heading", name="Home: 3 punti")).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="Home: 3 punti")).to_be_visible()
    page.get_by_text("Verifica e correzione manuale dei tiri", exact=True).click()
    review.get_by_role("button", name="Rivedi", exact=True).click()
    review.get_by_label("Esito").select_option("ShotMissed")
    review.get_by_role("button", name="Salva tiro").click()
    expect(page.get_by_role("heading", name="Home: 0 punti")).to_be_visible()
    review.get_by_role("button", name="Rivedi", exact=True).click()
    review.get_by_role("button", name="Scarta tiro").click()
    expect(review.get_by_role("button", name="Scartati (1)")).to_be_visible()
    fail_report = True
    review.get_by_role("button", name="Aggiungi tiro dalla posizione del video").click()
    review.get_by_role("button", name="Salva tiro").click()
    expect(review.get_by_role("alert")).to_contain_text("report")
    expect(review.get_by_role("button", name="Aggiungi tiro dalla posizione del video")).to_be_disabled()
    assert posts == 2
    fail_report = False
    review.get_by_role("button", name="Ricarica report").click()
    expect(review.get_by_role("button", name="Aggiungi tiro dalla posizione del video")).to_be_enabled()
    with page.expect_download() as downloaded:
        page.get_by_role("button", name="Esporta report CSV").click()
    assert downloaded.value.suggested_filename.endswith(".csv")
    page.set_viewport_size({"width": 390, "height": 844})
    review.get_by_role("button", name="Aggiungi tiro dalla posizione del video").click()
    overflow = page.evaluate("""[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,text:e.textContent.slice(0,60)})).slice(0,12)""")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"Mobile overflow: {overflow}"
    assert not errors, errors
    browser.close()
print("PASS: assisted start, timestamp, save, refresh, correction, rejection, report retry without duplicate, CSV, mobile")
