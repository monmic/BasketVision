"""Disposable DB/API/real-worker smoke. Never connects to the application DB."""
import json
import os
import secrets
import sys
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
RUN = uuid.uuid4().hex[:10]
OUT = ROOT/'artifacts/tester-pilot-20261029'/('runtime-'+RUN)
OUT.mkdir(parents=True)
network = 'basketvision-pilot-'+RUN
containers = []
token = None
base = 'http://127.0.0.1:18080'


def command(args, env=None):
    result = subprocess.run(args,capture_output=True,text=True,env=env,timeout=180)
    if result.returncode:
        raise RuntimeError(f'{args[0]} operation failed: {result.stderr[-1200:]}')
    return result.stdout.strip()


def launch(args, env=None):
    identity = command(['docker','run','-d','--label','basketvision.pilot='+RUN,*args],env)
    assert len(identity) == 64 and all(c in '0123456789abcdef' for c in identity)
    containers.append(identity)
    return identity


def request(path, method='GET', body=None, headers=None):
    headers = dict(headers or {})
    if token:
        headers['Authorization'] = 'Bearer '+token
    if isinstance(body,dict):
        body = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    with urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=headers,method=method),timeout=20) as response:
        data = response.read()
        return response.status,json.loads(data) if 'application/json' in response.headers.get('Content-Type','') else data


def until(operation, timeout=120):
    end = time.monotonic()+timeout
    last = None
    while time.monotonic() < end:
        try:
            last = operation()
            if last:
                return last
        except (OSError,ValueError):
            pass
        time.sleep(.25)
    raise AssertionError(f'Timed out waiting for disposable service/state: {last}')


try:
    command(['docker','network','create','--label','basketvision.pilot='+RUN,network])
    db = launch(['--network',network,'--network-alias','pilot-db','-p','127.0.0.1:5544:5432',
                 '--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_USER=test','-e','POSTGRES_PASSWORD=test',
                 '-e','POSTGRES_DB=basketvision_tests','postgres:16-alpine'])
    until(lambda: subprocess.run(['docker','exec',db,'pg_isready','-U','test','-d','basketvision_tests'],capture_output=True).returncode == 0)
    command(['docker','exec',db,'createdb','-U','test','pilot_runtime'])
    # Current source assemblies, a tmpfs database, and isolated storage only.
    env = dict(os.environ,Auth__SigningKey=secrets.token_hex(48),Seed__Demo__Email='pilot-'+RUN+'@test.local',
               Seed__Demo__Password='P!'+secrets.token_hex(20)+'9a')
    api = launch(['--network',network,'-p','127.0.0.1:18080:8080',
                  '-e','ConnectionStrings__Default=Host=pilot-db;Database=pilot_runtime;Username=test;Password=test',
                  '-e','Auth__SigningKey','-e','Auth__SecureCookies=false','-e','Seed__Demo__Email','-e','Seed__Demo__Password',
                  '-e','Storage__Root=/app/storage','-v',str(OUT)+':/app/storage',
                  '-v',str(ROOT/'src/BasketVision.Api/bin/Debug/net8.0')+':/pilot:ro',
                  '--entrypoint','dotnet','basketvision-api','/pilot/BasketVision.Api.dll'],env)
    until(lambda: request('/health')[0] == 200)
    # Relevant backend contracts use their own accounts/temp storage on this DB.
    test_env = dict(os.environ,TEST_DATABASE_URL='Host=127.0.0.1;Port=5544;Database=basketvision_tests;Username=test;Password=test')
    result = '' if '--skip-backend-tests' in sys.argv else command(['dotnet','test',str(ROOT/'tests/BasketVision.Tests/BasketVision.Tests.csproj'),'--no-build',
                      '--filter','FullyQualifiedName~AuthorizationTests|FullyQualifiedName~ShootingTests|FullyQualifiedName~ReportExportTests',
                      '--logger','console;verbosity=minimal'],test_env)
    print(result,flush=True)
    print('Disposable API and focused backend tests ready',flush=True)
    _,login = request('/auth/login','POST',dict(email=env['Seed__Demo__Email'],password=env['Seed__Demo__Password']))
    token = login['accessToken']
    _,game = request('/api/games','POST',dict(name='Disposable pilot',teamAName='Home',teamBName='Away'))
    command(['docker','run','--rm','--network','none','-v',str(OUT)+':/out','--entrypoint','ffmpeg','basketvision-api',
             '-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=black:s=854x480:r=15','-t','8',
             '-c:v','libx264','-pix_fmt','yuv420p','/out/pilot.mp4'])
    boundary = uuid.uuid4().hex
    video = (OUT/'pilot.mp4').read_bytes()
    upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="pilot.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
              +video+f'\r\n--{boundary}--\r\n'.encode())
    request(f'/api/games/{game["id"]}/video','POST',upload,{'Content-Type':'multipart/form-data; boundary='+boundary})
    status,part = request(f'/api/games/{game["id"]}/video',headers={'Range':'bytes=0-31'})
    assert status == 206 and len(part) == 32
    _,created = request(f'/api/games/{game["id"]}/analysis','POST',dict(startSeconds=1,endSeconds=7))
    job_id = created['analysisId']
    worker = launch(['--network',network,'--cpus','2',
                     '-e','DATABASE_URL=postgresql://test:test@pilot-db:5432/pilot_runtime','-e','ANALYSIS_MODE=vision',
                     '-e','VISION_CPU_THREADS=2','-e','YOLO_CONFIG_DIR=/tmp/ultralytics','-e','BALL_DEBUG_EXPORT=true',
                     '-v',str(REPO/'vision/worker.py')+':/app/worker.py:ro',
                     '-v',str(REPO/'vision/camera_motion.py')+':/app/camera_motion.py:ro',
                     '-v',str(REPO/'vision/shot_detector.py')+':/app/shot_detector.py:ro',
                     '-v',str(REPO/'vision/person_tracker_diagnostic.yaml')+':/app/person_tracker_diagnostic.yaml:ro',
                     '-v',str(OUT)+':/app/storage',
                     '-v',str(REPO/'storage/diagnostics/models/yolo26n.pt')+':/app/yolo26n.pt:ro',
                     '--entrypoint','python','basketvision-worker','/app/worker.py'])
    def progressed():
        _,state = request('/api/analysis/'+job_id)
        assert state['status'] != 'Failed',state.get('error')
        return state if state['status'] == 'Processing' and state['progress'] > 0 else None
    state = until(progressed)
    request('/api/analysis/'+job_id+'/pause','POST')
    checkpoint = OUT/'analysis'/(job_id+'.checkpoint.json')
    until(lambda: f'Analysis {job_id} paused at' in command(['docker','logs',worker]))
    # Worker acknowledges the pause via a persisted checkpoint before resume.
    paused_checkpoint = until(lambda: json.loads(checkpoint.read_text()))
    assert paused_checkpoint
    request('/api/analysis/'+job_id+'/resume','POST')
    def completed():
        _,state = request('/api/analysis/'+job_id)
        assert state['status'] != 'Failed',state.get('error')
        return state['status'] == 'Completed'
    until(completed)
    _,vision = request('/api/analysis/'+job_id+'/vision')
    assert vision['video']['analysisStartSeconds'] == 1
    assert vision['video']['analysisEndSeconds'] == 7
    assert all(1 <= p['timestamp'] <= 7 for p in vision['ballTrack'])
    assert vision['video']['processedFrames'] > 0
    assert vision['video']['processedBallFrames'] == 90, 'Resume must not recount the checkpoint frame'
    assert vision['video']['processedPersonFrames'] == 30
    assert all(1 <= p['timestamp'] <= 7 for p in vision.get('debugFrames',[]))
    _,me = request('/auth/me')
    assert me['usage']['analysesStarted'] == 1
    assert abs(me['usage']['analyzedMinutes']-.1) < .001
    request('/api/analysis/'+job_id,'DELETE')
    assert not checkpoint.exists()
    assert not (OUT/'analysis'/(job_id+'.json')).exists()
    assert request(f'/api/games/{game["id"]}/video')[0] == 200
    (ROOT/'artifacts/tester-pilot-20261029/stack-result.json').write_text(json.dumps(dict(passed=True,
        processedFrames=vision['video']['processedFrames'],range=[1,7],realPauseResume=True,usageChargedOnce=True)))
    print('PASS: real upload/probe, authenticated streaming, worker progress, checkpoint pause/resume, absolute range, result, usage, delete preserving video',flush=True)
except Exception:
    for i,identity in enumerate(containers):
        logs = subprocess.run(['docker','logs',identity],capture_output=True,text=True)
        (OUT/f'service-{i}.log').write_text(logs.stdout+'\n'+logs.stderr,encoding='utf-8')
    raise
finally:
    # Include a container created by Docker even if its start/mount failed.
    owned = command(['docker','ps','-aq','--no-trunc','--filter','label=basketvision.pilot='+RUN]).splitlines()
    for identity in reversed(owned):
        label = command(['docker','inspect','--format','{{index .Config.Labels "basketvision.pilot"}}',identity])
        assert label == RUN
        command(['docker','rm','-f',identity])
    subprocess.run(['docker','network','rm',network],capture_output=True)
