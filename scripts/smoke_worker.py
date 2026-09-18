"""Full-stack smoke against the disposable API at localhost:18080, never the main API."""
from pathlib import Path
import json
import time
import urllib.request
import uuid

root = Path(__file__).resolve().parents[1]
settings = dict(line.split("=", 1) for line in (root / ".env").read_text().splitlines()
                if line and not line.startswith("#") and "=" in line)
base = "http://localhost:18080"
token = None

def request(path, method="GET", body=None, headers=None):
    headers = dict(headers or {})
    if token:
        headers["Authorization"] = "Bearer " + token
    if isinstance(body, dict):
        body = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=headers, method=method), timeout=30) as response:
        data = response.read()
        return response.status, json.loads(data) if "application/json" in response.headers.get("Content-Type", "") else data

_, login = request("/auth/login", "POST", {"email": settings["SEED_DEMO_EMAIL"], "password": settings["SEED_DEMO_PASSWORD"]})
token = login["accessToken"]
_, game = request("/api/games", "POST", {"name": "Disposable auth smoke", "teamAName": "A", "teamBName": "B"})
game_id = game["id"]
boundary = uuid.uuid4().hex
video = (root / "storage/backups/auth-smoke-video.mp4").read_bytes()
body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="smoke.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
        + video + f'\r\n--{boundary}--\r\n'.encode())
_, upload = request(f"/api/games/{game_id}/video", "POST", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
status, data = request(f"/api/games/{game_id}/video", headers={"Range": "bytes=0-31"})
assert status == 206 and len(data) == 32
status, job = request(f"/api/games/{game_id}/analysis", "POST", {"startSeconds": 0, "endSeconds": 1})
assert status == 202
job_id = job["analysisId"]
request(f"/api/analysis/{job_id}/pause", "POST")
request(f"/api/analysis/{job_id}/resume", "POST")
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    _, job = request(f"/api/analysis/{job_id}")
    assert job["status"] != "Failed", job.get("error")
    if job["status"] == "Completed":
        break
    time.sleep(1)
else:
    raise AssertionError("Worker did not complete the disposable job in 180 seconds")
_, vision = request(f"/api/analysis/{job_id}/vision")
assert vision["mode"] == "vision-cv02.4"
_, me = request("/auth/me")
assert me["usage"]["analysesStarted"] == 1
assert abs(me["usage"]["analyzedMinutes"] - 1 / 60) < 0.001
request(f"/api/analysis/{job_id}", "DELETE")
_, me = request("/auth/me")
assert me["usage"]["analysesStarted"] == 1
request("/auth/logout", "POST")
# The disposable database is removed separately; delete only this generated video.
uploaded = root / "storage/videos" / Path(upload["videoPath"]).name
assert uploaded.resolve().parent == (root / "storage/videos").resolve()
assert uploaded.name.startswith(game_id + "-")
uploaded.unlink()
print("Full-stack smoke passed: real upload/ffprobe, streaming, authorized job, pause/resume, CV worker, vision report, usage and deletion.")
