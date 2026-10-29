"""Automatic tester journey against built UI, isolated API fixtures only."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5174'
game = dict(id='pilot-game',name='Pilot Home vs Away',teams=[dict(id='home',name='Home',side='A'),dict(id='away',name='Away',side='B')])
jobs = []
vision_fails = True
held_upload = None
hold_poll = False
held_poll = None
starts = 0
poll_failure_once = False


def api(route):
    global held_upload, held_poll, starts, poll_failure_once
    path = urlparse(route.request.url).path
    method = route.request.method
    body,status = {},200
    if path == '/auth/refresh':
        body = dict(accessToken='fixture-only')
    elif path == '/auth/me':
        body = dict(id='pilot-user',email='pilot@test.local',roles=['User'],plan='Fixture',bypass=True,entitlements={},
                    usage=dict(analysesStarted=0,reservedMinutes=0,analyzedMinutes=0,storageBytes=0))
    elif path == '/api/games':
        body = [game]
    elif path == '/api/games/pilot-game':
        body = game
    elif path.endswith('/video'):
        if method == 'POST':
            held_upload = route
            return
        route.fulfill(status=204,body='')
        return
    elif path == '/api/analysis/active':
        body = [dict(j,gameName=game['name']) for j in jobs if j['status'] in ('Pending','Processing','Paused')]
    elif path.endswith('/analyses'):
        body = jobs
    elif path.endswith('/analysis') and method == 'POST':
        starts += 1
        request = route.request.post_data_json
        assert request['startSeconds'] == 60 and request['endSeconds'] == 70
        body = dict(analysisId='pilot-job',gameId=game['id'],status='Processing',progress=42,
                    startSeconds=60,endSeconds=70,createdAtUtc='2026-10-29T10:00:00Z')
        jobs.append(body)
        status = 202
    elif path.endswith('/report'):
        body = dict(gameId=game['id'],gameName=game['name'],events=[dict(id='candidate',type='ShotCandidate',teamId=None,
                    analysisJobId='pilot-job',videoTimestamp=65,confidence=.4,status='NeedsReview')],teams=[dict(teamId=t['id'],teamName=t['name'],stats={'ShotMade':0},
                     shooting=dict(points=0,unspecified=0,categories=[])) for t in game['teams']])
    elif path.endswith('/pause') or path.endswith('/resume'):
        job = next(j for j in jobs if j['analysisId'] == path.split('/')[-2])
        job['status'] = 'Paused' if path.endswith('/pause') else 'Processing'
        body = job
    elif path.endswith('/vision'):
        if vision_fails:
            status,body = 503,dict(message='Fixture result unavailable')
        else:
            body = dict(analysisId=path.split('/')[-2],gameId=game['id'],mode='vision-cv02.4',model='fixture',
                        video=dict(fps=30,totalFrames=300,width=854,height=480,durationSeconds=80,
                                   analysisStartSeconds=60,analysisEndSeconds=70,frameStride=1,processedFrames=300),
                        summary=dict(personDetections=50,ballDetections=12,framesWithBall=8,maxPersonsInFrame=10,
                                     uniquePersonTracks=10,uniqueBallTracks=2,storedBallPoints=12),ballTrack=[])
    elif path.startswith('/api/analysis/'):
        if poll_failure_once and path.endswith('/pilot-job'):
            poll_failure_once = False
            route.abort('failed')
            return
        if hold_poll and path.endswith('/pilot-job'):
            held_poll = route
            return
        body = next(j for j in jobs if j['analysisId'] == path.split('/')[-1])
    else:
        raise AssertionError(f'Unexpected fixture request {method} {path}')
    route.fulfill(status=status,content_type='application/json',body=json.dumps(body))


with sync_playwright() as pw:
    executable = os.environ.get('BASKETVISION_BROWSER')
    browser = pw.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
    page = browser.new_page(viewport=dict(width=1280,height=900))
    errors = []
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/auth/**',api)
    page.route('**/api/**',api)
    page.goto(base+'/?game=pilot-game')
    page.locator('input[type=file]').set_input_files(dict(name='pilot.mp4',mimeType='video/mp4',buffer=b'isolated-upload-fixture'))
    page.get_by_role('button',name='Carica video',exact=True).click()
    expect(page.get_by_role('button',name='Caricamento...',exact=True)).to_be_disabled()
    assert held_upload is not None
    expect(page.locator('input[type=file]')).to_be_disabled()
    held_upload.abort('failed')
    expect(page.get_by_role('alert')).to_contain_text('Il file selezionato è conservato')
    expect(page.get_by_text('pilot.mp4',exact=True)).to_be_visible()
    held_upload = None
    page.get_by_role('button',name='Carica video',exact=True).click()
    assert held_upload is not None
    game['videoPath'] = 'fixture.mp4'
    held_upload.fulfill(status=200,content_type='application/json',body=json.dumps(dict(videoPath='fixture.mp4')))
    expect(page.get_by_text('Video caricato ✓',exact=True)).to_be_visible()
    page.get_by_label('DA',exact=True).fill('00:01:00')
    page.get_by_label('A',exact=True).fill('00:01:10')
    page.get_by_role('button',name='Avvia analisi CV',exact=True).click()
    expect(page).to_have_url(base+'/?game=pilot-game&analysis=pilot-job')
    page.locator('.analysis-controls').get_by_role('button',name='Pausa',exact=True).click()
    expect(page.get_by_text('Analisi in pausa',exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_text('Analisi in pausa',exact=True)).to_be_visible()
    expect(page.get_by_label('DA',exact=True)).to_have_value('00:01:00')
    expect(page.get_by_label('A',exact=True)).to_have_value('00:01:10')
    poll_failure_once = True
    page.locator('.analysis-controls').get_by_role('button',name='Riprendi',exact=True).click()
    expect(page.get_by_text('Analisi CV in corso',exact=True)).to_be_visible()
    expect(page.get_by_role('status')).to_contain_text('Riprovo automaticamente')
    jobs[0].update(status='Completed',progress=100)
    expect(page.get_by_text('Analisi completata',exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_role('button',name='Riprova risultato',exact=True)).to_be_visible()
    vision_fails = False
    page.get_by_role('button',name='Riprova risultato',exact=True).click()
    expect(page.get_by_role('heading',name='Risultato dell’analisi',exact=True)).to_be_visible()
    expect(page.get_by_text('300 fotogrammi elaborati',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='Punti e percentuali',exact=True)).not_to_be_visible()
    expect(page.get_by_role('heading',name='Statistiche eventi',exact=True)).not_to_be_visible()
    page.get_by_role('button').filter(has_text='Candidato di tiro').click()
    assert page.locator('video').evaluate('v => v.currentTime') == 65
    expect(page.get_by_text('Strumenti di verifica manuale',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='Inizia revisione assistita',exact=True)).not_to_be_visible()
    assert starts == 1
    jobs[0]['status'] = 'Paused'
    jobs.insert(0,dict(jobs[0],analysisId='newer-job',status='Completed',createdAtUtc='2026-10-29T11:00:00Z'))
    page.goto(base+'/?game=pilot-game&analysis=newer-job')
    expect(page.get_by_label('Sessione visualizzata')).to_have_value('newer-job')
    page.locator('.job-open').click()
    expect(page.get_by_label('Sessione visualizzata')).to_have_value('pilot-job')
    # A late status response must not replace the newly selected session.
    hold_poll = True
    for _ in range(25):
        if held_poll is not None:
            break
        page.wait_for_timeout(200)
    assert held_poll is not None
    page.get_by_label('Sessione visualizzata').select_option('newer-job')
    held_poll.fulfill(status=200,content_type='application/json',body=json.dumps(jobs[1]))
    page.wait_for_timeout(200)
    expect(page.get_by_label('Sessione visualizzata')).to_have_value('newer-job')
    page.set_viewport_size(dict(width=390,height=844))
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow'
    out = Path(__file__).resolve().parents[1]/'artifacts/tester-pilot-20261029'
    page.screenshot(path=str(out/'pilot-mobile.png'),full_page=True)
    assert not errors,errors
    browser.close()
print('PASS: upload, range, pause/resume, reload, result retry, experimental summary, exact background job, stale polling, mobile')
