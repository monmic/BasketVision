"""Generate isolated tracker experiment; never modify the operational worker."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE.parents[2] / 'vision' / 'worker.py'
text = source.read_text(encoding='utf-8')
old = 'or float(detection["confidence"]) < BALL_TRACK_NEW_MIN_CONFIDENCE)'
assert text.count(old) == 2
text = text.replace(old, old[:-1] + '\n                           or detection.get("semanticBall") is False)')
old = 'and float(detection["confidence"]) >= BALL_TRACK_NEW_MIN_CONFIDENCE)'
assert text.count(old) == 1
text = text.replace(old, old[:-1] + '\n                               and detection.get("semanticBall") is not False)')
(HERE / 'worker-semantic-prototype.py').write_text(text, encoding='utf-8')
