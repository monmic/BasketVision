import json
import math
import os
import random
import statistics
import time
import uuid
from pathlib import Path

import cv2
import psycopg
from ultralytics import YOLO

DSN = os.getenv("DATABASE_URL", "postgresql://basketvision:basketvision@db:5432/basketvision")
ANALYSIS_MODE = os.getenv("ANALYSIS_MODE", "vision").lower()
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolo26n.pt")
BALL_MODEL = os.getenv("BALL_MODEL", YOLO_MODEL)

PERSON_FRAME_STRIDE = max(1, int(os.getenv("PERSON_FRAME_STRIDE", os.getenv("FRAME_STRIDE", "3"))))
PERSON_CONFIDENCE = float(os.getenv("PERSON_CONFIDENCE", "0.10"))
PERSON_IMGSZ = max(320, int(os.getenv("PERSON_IMGSZ", "640")))
PERSON_TRACKER_CONFIG = os.getenv("PERSON_TRACKER_CONFIG", "person_tracker_diagnostic.yaml")

BALL_FRAME_STRIDE = max(1, int(os.getenv("BALL_FRAME_STRIDE", "1")))
BALL_CONFIDENCE = float(os.getenv("BALL_CONFIDENCE", "0.02"))
BALL_IMGSZ = max(320, int(os.getenv("BALL_IMGSZ", "960")))
BALL_USE_TILES = os.getenv("BALL_USE_TILES", "true").lower() in {"1", "true", "yes", "on"}
BALL_TILE_STRIDE = max(1, int(os.getenv("BALL_TILE_STRIDE", "3")))
BALL_TILE_OVERLAP = min(0.45, max(0.0, float(os.getenv("BALL_TILE_OVERLAP", "0.15"))))
BALL_TILE_IMGSZ = max(320, int(os.getenv("BALL_TILE_IMGSZ", "640")))
BALL_TRACK_MAX_GAP_SECONDS = max(0.05, float(os.getenv("BALL_TRACK_MAX_GAP_SECONDS", "1.5")))
BALL_TRACK_BASE_DISTANCE_PX = max(5.0, float(os.getenv("BALL_TRACK_BASE_DISTANCE_PX", "45")))
BALL_TRACK_MAX_SPEED_PX_PER_SECOND = max(50.0, float(os.getenv("BALL_TRACK_MAX_SPEED_PX_PER_SECOND", "1200")))
BALL_TRACK_MIN_HITS = max(3, int(os.getenv("BALL_TRACK_MIN_HITS", "3")))
BALL_TRACK_MAX_MISSES = max(1, int(os.getenv("BALL_TRACK_MAX_MISSES", "6")))
BALL_TRACK_MAX_WEAK_UPDATES = max(0, int(os.getenv("BALL_TRACK_MAX_WEAK_UPDATES", "6")))
BALL_ACCEPTED_MIN_SCORE = max(0.001, float(os.getenv("BALL_ACCEPTED_MIN_SCORE", "0.025")))
BALL_TRACK_UPDATE_MIN_SCORE = max(0.001, float(os.getenv("BALL_TRACK_UPDATE_MIN_SCORE", "0.018")))
BALL_TRACK_NEW_MIN_SCORE = max(BALL_TRACK_UPDATE_MIN_SCORE, float(os.getenv("BALL_TRACK_NEW_MIN_SCORE", "0.080")))
BALL_TRACK_NEW_MIN_CONFIDENCE = max(BALL_CONFIDENCE, float(os.getenv("BALL_TRACK_NEW_MIN_CONFIDENCE", "0.10")))
BALL_STATIC_MIN_HITS = max(BALL_TRACK_MIN_HITS, int(os.getenv("BALL_STATIC_MIN_HITS", "6")))
BALL_STATIC_MAX_SPEED_PX_PER_SECOND = max(0.0, float(os.getenv("BALL_STATIC_MAX_SPEED_PX_PER_SECOND", "12")))
BALL_STATIC_PENALTY = min(1.0, max(0.0, float(os.getenv("BALL_STATIC_PENALTY", "0.35"))))
BALL_DEBUG_EXPORT = os.getenv("BALL_DEBUG_EXPORT", "false").lower() in {"1", "true", "yes", "on"}
BALL_DEBUG_MAX_FRAMES = max(0, int(os.getenv("BALL_DEBUG_MAX_FRAMES", "20")))
BALL_DEBUG_MIN_INTERVAL_SECONDS = max(0.0, float(os.getenv("BALL_DEBUG_MIN_INTERVAL_SECONDS", "1.0")))
BALL_DEBUG_JPEG_QUALITY = min(100, max(40, int(os.getenv("BALL_DEBUG_JPEG_QUALITY", "85"))))

MAX_BALL_POINTS = max(100, int(os.getenv("MAX_BALL_POINTS", "20000")))
ANALYSIS_DIR = Path(os.getenv("ANALYSIS_DIR", "/app/storage/analysis"))

EVENT_TYPE_VALUES = {
    "ShotMade": 0,
    "ShotMissed": 1,
    "OffensiveRebound": 4,
    "DefensiveRebound": 5,
    "Turnover": 6,
    "Steal": 7,
    "Assist": 8,
    "Block": 9,
}

_person_model = None
_ball_model = None


def get_person_model():
    global _person_model
    if _person_model is None:
        print(f"Loading person model: {YOLO_MODEL}", flush=True)
        _person_model = YOLO(YOLO_MODEL)
    return _person_model


def get_ball_model():
    global _ball_model
    if _ball_model is None:
        # Keep inference predictors isolated: person tracking callbacks must never
        # observe full/tiled ball inference with different classes and dimensions.
        print(f"Loading isolated ball model: {BALL_MODEL}", flush=True)
        _ball_model = YOLO(BALL_MODEL)
    return _ball_model


def wait_for_db():
    while True:
        try:
            with psycopg.connect(DSN):
                return
        except Exception as exc:
            print(f"DB not ready: {exc}", flush=True)
            time.sleep(2)


def set_job(job_id, *, status=None, progress=None, error=None, completed=False):
    assignments = []
    params = []
    if status is not None:
        assignments.append('"Status" = %s')
        params.append(status)
    if progress is not None:
        assignments.append('"Progress" = %s')
        params.append(progress)
    if error is not None:
        assignments.append('"Error" = %s')
        params.append(error)
    if completed:
        assignments.append('"CompletedAtUtc" = NOW()')
    if not assignments:
        return
    params.append(job_id)
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(f'UPDATE "AnalysisJobs" SET {", ".join(assignments)} WHERE "Id" = %s', params)
            conn.commit()


def get_job_status(job_id):
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "Status" FROM "AnalysisJobs" WHERE "Id" = %s', (job_id,))
            row = cur.fetchone()
            return None if row is None else int(row[0])


def checkpoint_path(job_id):
    return ANALYSIS_DIR / f"{job_id}.checkpoint.json"


def save_checkpoint(job_id, data):
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    path = checkpoint_path(job_id)
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def load_checkpoint(job_id):
    path = checkpoint_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f"Invalid checkpoint for {job_id}: {exc}", flush=True)
        return None


def delete_checkpoint(job_id):
    path = checkpoint_path(job_id)
    if path.exists():
        path.unlink()


def claim_job():
    with psycopg.connect(DSN, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT j."Id", j."GameId", g."VideoPath"
                FROM "AnalysisJobs" j
                JOIN "Games" g ON g."Id" = j."GameId"
                WHERE j."Status" = 0
                ORDER BY j."CreatedAtUtc"
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            ''')
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            job_id, game_id, video_path = row
            cur.execute('UPDATE "AnalysisJobs" SET "Status" = 1, "Progress" = CASE WHEN "Progress" = 0 THEN 1 ELSE "Progress" END, "Error" = NULL WHERE "Id" = %s', (job_id,))
            conn.commit()
            return job_id, game_id, video_path


def process_mock(job_id, game_id):
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "Id" FROM "Teams" WHERE "GameId" = %s ORDER BY "Side"', (game_id,))
            teams = [r[0] for r in cur.fetchall()]

    for p in (25, 45, 70, 90):
        time.sleep(1)
        set_job(job_id, progress=p)

    mock = [
        (18.0, "ShotMissed", 0), (20.4, "DefensiveRebound", 1),
        (41.2, "Turnover", 1), (42.0, "Steal", 0),
        (47.5, "Assist", 0), (48.1, "ShotMade", 0),
        (72.0, "ShotMissed", 1), (73.3, "OffensiveRebound", 1),
        (80.2, "ShotMade", 1), (99.8, "Block", 0)
    ]

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            for ts, etype, ti in mock:
                team_id = teams[ti] if len(teams) > ti else None
                confidence = round(random.uniform(0.72, 0.98), 3)
                cur.execute('''INSERT INTO "GameEvents" ("Id","GameId","AnalysisJobId","Type","TeamId","VideoTimestamp","EndTimestamp","Confidence","Status","MetadataJson")
                    VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,0,%s)''',
                    (uuid.uuid4(), game_id, job_id, EVENT_TYPE_VALUES[etype], team_id, ts, confidence, '{"source":"mock"}'))
            conn.commit()

    set_job(job_id, status=2, progress=100, completed=True)
    print(f"Completed mock analysis {job_id}", flush=True)


def load_analysis_range(job_id):
    request_path = ANALYSIS_DIR / f"{job_id}.request.json"
    if not request_path.exists():
        return 0.0, None
    try:
        data = json.loads(request_path.read_text(encoding="utf-8"))
        start = max(0.0, float(data.get("startSeconds") or 0.0))
        raw_end = data.get("endSeconds")
        end = float(raw_end) if raw_end is not None else None
        return start, end
    except Exception as exc:
        print(f"Invalid analysis range for {job_id}: {exc}; using full video", flush=True)
        return 0.0, None


def _extract_boxes(result, class_id, source, timestamp, x_offset=0.0, y_offset=0.0):
    items = []
    if not result or result.boxes is None:
        return items
    for box in result.boxes:
        if int(box.cls.item()) != class_id:
            continue
        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = [float(v) for v in xyxy]
        x1 += x_offset; x2 += x_offset
        y1 += y_offset; y2 += y_offset
        items.append({
            "timestamp": round(timestamp, 3),
            "trackId": None,
            "confidence": round(float(box.conf.item()), 4),
            "source": source,
            "x1": round(x1, 1), "y1": round(y1, 1),
            "x2": round(x2, 1), "y2": round(y2, 1),
            "centerX": round((x1 + x2) / 2, 1),
            "centerY": round((y1 + y2) / 2, 1),
            "width": round(x2 - x1, 1),
            "height": round(y2 - y1, 1),
        })
    return items


def _nms_ball_candidates(candidates, score_threshold):
    if len(candidates) <= 1:
        return candidates
    boxes = []
    scores = []
    for c in candidates:
        boxes.append([float(c["x1"]), float(c["y1"]), max(1.0, float(c["x2"] - c["x1"])), max(1.0, float(c["y2"] - c["y1"]))])
        scores.append(float(c["confidence"]))
    idxs = cv2.dnn.NMSBoxes(boxes, scores, score_threshold=max(0.001, score_threshold), nms_threshold=0.35)
    if idxs is None or len(idxs) == 0:
        return []
    keep = []
    for idx in idxs:
        if hasattr(idx, "__len__"):
            idx = idx[0]
        keep.append(candidates[int(idx)])
    return keep


def _soft_ball_score(candidate):
    """Penalize implausible geometry without hard-rejecting blur or tiny balls."""
    width = max(1.0, float(candidate["width"]))
    height = max(1.0, float(candidate["height"]))
    area = width * height
    aspect = min(width, height) / max(width, height)

    # Motion blur may make a real ball elongated, so both penalties have floors.
    aspect_penalty = 0.45 + 0.55 * min(1.0, aspect / 0.65)
    if area < 25.0:
        size_penalty = max(0.45, area / 25.0)
    elif area > 1600.0:
        size_penalty = max(0.35, 1600.0 / area)
    else:
        size_penalty = 1.0

    candidate["aspectRatio"] = round(width / height, 3)
    candidate["softAspectPenalty"] = round(aspect_penalty, 4)
    candidate["softSizePenalty"] = round(size_penalty, 4)
    candidate["qualityScore"] = round(float(candidate["confidence"]) * aspect_penalty * size_penalty, 5)
    return candidate


def merge_ball_candidates(candidates):
    merged = _nms_ball_candidates(candidates, BALL_CONFIDENCE)
    return [_soft_ball_score(candidate) for candidate in merged]


def _draw_ball_candidates(frame, candidates, color, category, thickness):
    for candidate in candidates:
        x1, y1 = int(candidate["x1"]), int(candidate["y1"])
        x2, y2 = int(candidate["x2"]), int(candidate["y2"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        track_id = candidate.get("trackId")
        score = candidate.get("acceptedScore", candidate.get("qualityScore", candidate["confidence"]))
        reason = candidate.get("acceptanceReason", candidate.get("rejectionReason", "raw"))
        label = (f"{category} id={track_id if track_id is not None else '-'} "
                 f"c={candidate['confidence']:.2f} s={score:.3f} {reason}")
        cv2.putText(frame, label, (max(0, x1), max(14, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.38, color, 1, cv2.LINE_AA)


def export_ball_debug_frame(job_id, frame, timestamp, raw, accepted, rejected, sequence):
    debug_dir = ANALYSIS_DIR / f"{job_id}.debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    annotated = frame.copy()
    _draw_ball_candidates(annotated, raw, (0, 210, 255), "raw", 1)
    _draw_ball_candidates(annotated, rejected, (40, 40, 230), "rejected", 2)
    _draw_ball_candidates(annotated, accepted, (40, 210, 40), "accepted", 2)
    cv2.putText(annotated, "raw=yellow  accepted=green  rejected=red", (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
    file_name = f"accepted-{sequence:03d}-{timestamp:.3f}.jpg"
    output_path = debug_dir / file_name
    if not cv2.imwrite(str(output_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, BALL_DEBUG_JPEG_QUALITY]):
        raise RuntimeError(f"Cannot write debug frame: {output_path}")
    return {
        "fileName": file_name,
        "timestamp": round(timestamp, 3),
        "rawCandidates": len(raw),
        "acceptedDetections": len(accepted),
        "rejectedCandidates": len(rejected),
    }


def _histogram_median(histogram, count):
    if count <= 0:
        return 0.0
    target = (count + 1) // 2
    seen = 0
    for index, value in enumerate(histogram):
        seen += int(value)
        if seen >= target:
            return index / 100.0
    return 1.0


def detect_ball_full(model, frame, timestamp):
    results = model.predict(
        frame,
        classes=[32],
        conf=BALL_CONFIDENCE,
        imgsz=BALL_IMGSZ,
        verbose=False,
    )
    return _extract_boxes(results[0] if results else None, 32, "full", timestamp)


def detect_ball_tiled(model, frame, timestamp):
    h, w = frame.shape[:2]
    overlap_x = int(w * BALL_TILE_OVERLAP / 2)
    overlap_y = int(h * BALL_TILE_OVERLAP / 2)
    mid_x = w // 2
    mid_y = h // 2
    tiles = [
        (0, 0, min(w, mid_x + overlap_x), min(h, mid_y + overlap_y)),
        (max(0, mid_x - overlap_x), 0, w, min(h, mid_y + overlap_y)),
        (0, max(0, mid_y - overlap_y), min(w, mid_x + overlap_x), h),
        (max(0, mid_x - overlap_x), max(0, mid_y - overlap_y), w, h),
    ]
    candidates = []
    for i, (x1, y1, x2, y2) in enumerate(tiles):
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        results = model.predict(
            crop,
            classes=[32],
            conf=BALL_CONFIDENCE,
            imgsz=BALL_TILE_IMGSZ,
            verbose=False,
        )
        candidates.extend(_extract_boxes(results[0] if results else None, 32, f"tile{i+1}", timestamp, x1, y1))
    return _nms_ball_candidates(candidates, BALL_CONFIDENCE)


class BallTracker:
    def __init__(self):
        self.next_id = 1
        self.tracks = {}
        self.confirmed_track_ids = set()
        self.static_track_ids = set()
        self.tracks_created = 0
        self.weak_track_updates = 0

    def restore(self, raw_tracks):
        if not isinstance(raw_tracks, dict):
            return
        restored = {}
        max_id = 0
        for key, val in raw_tracks.items():
            try:
                tid = int(key)
                restored_track = dict(val)
                points = int(restored_track.get("hits", restored_track.get("points", 0)))
                restored_track.setdefault("hits", points)
                restored_track.setdefault("consecutiveHits", points)
                restored_track.setdefault("misses", 0)
                restored_track.setdefault("consecutiveWeakHits", BALL_TRACK_MAX_WEAK_UPDATES)
                restored_track.setdefault("vx", 0.0)
                restored_track.setdefault("vy", 0.0)
                restored_track.setdefault("firstX", float(restored_track.get("x", 0.0)))
                restored_track.setdefault("firstY", float(restored_track.get("y", 0.0)))
                restored_track.setdefault("firstTimestamp", float(restored_track.get("lastTimestamp", 0.0)))
                restored_track.setdefault("pathLength", 0.0)
                restored_track.setdefault("state", "confirmed" if points >= BALL_TRACK_MIN_HITS else "tentative")
                restored[tid] = restored_track
                if restored_track["state"] == "confirmed":
                    self.confirmed_track_ids.add(tid)
                max_id = max(max_id, tid)
            except Exception:
                continue
        self.tracks = restored
        self.next_id = max_id + 1

    def snapshot(self):
        return {str(k): v for k, v in self.tracks.items()}

    def restore_confirmed_ids(self, raw_ids):
        if isinstance(raw_ids, list):
            self.confirmed_track_ids.update(int(value) for value in raw_ids)

    def restore_static_ids(self, raw_ids):
        if isinstance(raw_ids, list):
            self.static_track_ids.update(int(value) for value in raw_ids)

    def restore_diagnostics(self, raw):
        if isinstance(raw, dict):
            self.tracks_created = int(raw.get("tracksCreated", 0))
            self.weak_track_updates = int(raw.get("weakTrackUpdates", 0))

    def diagnostics(self):
        return {"tracksCreated": self.tracks_created, "weakTrackUpdates": self.weak_track_updates}

    @staticmethod
    def _prediction(track, timestamp):
        dt = max(0.0, timestamp - float(track["lastTimestamp"]))
        return float(track["x"]) + float(track["vx"]) * dt, float(track["y"]) + float(track["vy"]) * dt

    def update(self, detections, timestamp):
        expired = [tid for tid, track in self.tracks.items()
                   if timestamp - float(track["lastTimestamp"]) > BALL_TRACK_MAX_GAP_SECONDS]
        for tid in expired:
            del self.tracks[tid]

        available_tracks = set(self.tracks)
        available_detections = set(range(len(detections)))
        matches = []
        possible = []
        for tid in available_tracks:
            track = self.tracks[tid]
            predicted_x, predicted_y = self._prediction(track, timestamp)
            dt = max(0.001, timestamp - float(track["lastTimestamp"]))
            max_distance = BALL_TRACK_BASE_DISTANCE_PX + BALL_TRACK_MAX_SPEED_PX_PER_SECOND * dt
            for index, detection in enumerate(detections):
                is_weak = (float(detection["qualityScore"]) < BALL_TRACK_NEW_MIN_SCORE
                           or float(detection["confidence"]) < BALL_TRACK_NEW_MIN_CONFIDENCE)
                if is_weak and (track["state"] != "confirmed"
                                or int(track.get("consecutiveWeakHits", 0)) >= BALL_TRACK_MAX_WEAK_UPDATES):
                    continue
                distance = math.hypot(float(detection["centerX"]) - predicted_x,
                                      float(detection["centerY"]) - predicted_y)
                if distance <= max_distance:
                    possible.append((distance / max_distance, distance, tid, index))

        for _, distance, tid, index in sorted(possible):
            if tid not in available_tracks or index not in available_detections:
                continue
            available_tracks.remove(tid)
            available_detections.remove(index)
            matches.append((tid, index, distance))

        for tid, index, prediction_error in matches:
            track = self.tracks[tid]
            detection = detections[index]
            previous_x = float(track["x"])
            previous_y = float(track["y"])
            dt = max(0.001, timestamp - float(track["lastTimestamp"]))
            measured_vx = (float(detection["centerX"]) - previous_x) / dt
            measured_vy = (float(detection["centerY"]) - previous_y) / dt
            track["vx"] = 0.65 * float(track["vx"]) + 0.35 * measured_vx
            track["vy"] = 0.65 * float(track["vy"]) + 0.35 * measured_vy
            track["pathLength"] = float(track.get("pathLength", 0.0)) + math.hypot(
                float(detection["centerX"]) - previous_x, float(detection["centerY"]) - previous_y)
            track["x"] = detection["centerX"]
            track["y"] = detection["centerY"]
            track["lastTimestamp"] = timestamp
            track["hits"] = int(track.get("hits", 0)) + 1
            track["consecutiveHits"] = int(track.get("consecutiveHits", 0)) + 1
            track["misses"] = 0
            if track["hits"] >= BALL_TRACK_MIN_HITS and track["consecutiveHits"] >= BALL_TRACK_MIN_HITS:
                track["state"] = "confirmed"
                self.confirmed_track_ids.add(tid)
            elif track.get("state") == "lost":
                track["state"] = "tentative"
            detection["predictionErrorPx"] = round(prediction_error, 2)
            is_weak_update = (float(detection["qualityScore"]) < BALL_TRACK_NEW_MIN_SCORE
                              or float(detection["confidence"]) < BALL_TRACK_NEW_MIN_CONFIDENCE)
            if is_weak_update:
                self.weak_track_updates += 1
            track["consecutiveWeakHits"] = int(track.get("consecutiveWeakHits", 0)) + 1 if is_weak_update else 0
            detection["associationType"] = "weak-track-update" if is_weak_update else "strong-track-update"
            self._decorate_detection(detection, tid, track, timestamp, is_new=False)

        for tid in available_tracks:
            track = self.tracks[tid]
            track["misses"] = int(track.get("misses", 0)) + 1
            track["consecutiveHits"] = 0
            if track["state"] == "confirmed" or track["misses"] >= BALL_TRACK_MAX_MISSES:
                track["state"] = "lost"

        for index in available_detections:
            detection = detections[index]
            can_start_track = (float(detection["qualityScore"]) >= BALL_TRACK_NEW_MIN_SCORE
                               and float(detection["confidence"]) >= BALL_TRACK_NEW_MIN_CONFIDENCE)
            if not can_start_track:
                detection["accepted"] = False
                detection["acceptedScore"] = detection["qualityScore"]
                detection["rejectionReason"] = "weak_candidate_cannot_start_track"
                detection["associationType"] = "unmatched"
                continue
            tid = self.next_id
            self.next_id += 1
            self.tracks_created += 1
            track = {
                "x": detection["centerX"], "y": detection["centerY"], "vx": 0.0, "vy": 0.0,
                "firstX": detection["centerX"], "firstY": detection["centerY"],
                "firstTimestamp": timestamp, "lastTimestamp": timestamp,
                "hits": 1, "consecutiveHits": 1, "misses": 0, "pathLength": 0.0,
                "consecutiveWeakHits": 0,
                "state": "tentative",
            }
            self.tracks[tid] = track
            detection["associationType"] = "new-track"
            self._decorate_detection(detection, tid, track, timestamp, is_new=True)

        return detections

    def _decorate_detection(self, detection, tid, track, timestamp, is_new):
        duration = max(0.001, timestamp - float(track["firstTimestamp"]))
        average_speed = float(track.get("pathLength", 0.0)) / duration
        is_static = int(track["hits"]) >= BALL_STATIC_MIN_HITS and average_speed < BALL_STATIC_MAX_SPEED_PX_PER_SECOND
        if is_static:
            self.static_track_ids.add(tid)
        else:
            self.static_track_ids.discard(tid)
        static_penalty = BALL_STATIC_PENALTY if is_static else 1.0
        detection["trackId"] = tid
        detection["trackState"] = track["state"]
        detection["trackHits"] = int(track["hits"])
        detection["trackAverageSpeedPxPerSecond"] = round(average_speed, 2)
        detection["staticPenalty"] = static_penalty
        detection["acceptedScore"] = round(float(detection["qualityScore"]) * static_penalty, 5)
        detection["accepted"] = False
        if is_new:
            detection["rejectionReason"] = "new_track_requires_temporal_confirmation"
        elif track["state"] != "confirmed":
            detection["rejectionReason"] = "track_not_temporally_confirmed"
        elif detection["acceptedScore"] < BALL_ACCEPTED_MIN_SCORE:
            detection["rejectionReason"] = "final_score_below_acceptance_threshold"
        else:
            detection["accepted"] = True
            detection["acceptanceReason"] = "confirmed_track_temporal_association"

    def confirmed_count(self):
        return len(self.confirmed_track_ids)


def process_vision(job_id, game_id, video_path):
    if not video_path:
        raise RuntimeError("Game has no video path")
    if not Path(video_path).exists():
        raise RuntimeError(f"Video not found in worker container: {video_path}")

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV cannot open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = total_frames / fps if fps > 0 else 0
    start_seconds, requested_end_seconds = load_analysis_range(job_id)
    end_seconds = min(requested_end_seconds, duration) if requested_end_seconds is not None and duration > 0 else requested_end_seconds
    if duration > 0:
        start_seconds = min(start_seconds, duration)
    if end_seconds is not None and end_seconds <= start_seconds:
        raise RuntimeError("Invalid analysis range after clamping to video duration")

    start_frame = int(start_seconds * fps) if fps > 0 else 0
    end_frame = int(end_seconds * fps) if end_seconds is not None and fps > 0 else total_frames
    range_frames = max(1, end_frame - start_frame) if total_frames > 0 else 1

    checkpoint = load_checkpoint(job_id) or {}
    resume_seconds = max(start_seconds, float(checkpoint.get("resumeTimestamp", start_seconds) or start_seconds))
    resume_frame = int(resume_seconds * fps) if fps > 0 else start_frame
    if resume_seconds > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, resume_seconds * 1000.0)

    person_model = get_person_model()
    ball_model = get_ball_model()
    frame_index = resume_frame
    processed_person_frames = int(checkpoint.get("processedPersonFrames", 0))
    processed_ball_frames = int(checkpoint.get("processedBallFrames", 0))
    person_detections = int(checkpoint.get("personDetections", 0))
    raw_ball_candidates = int(checkpoint.get("rawBallCandidates", checkpoint.get("ballDetections", 0)))
    accepted_ball_detections = int(checkpoint.get("acceptedBallDetections", checkpoint.get("ballDetections", 0)))
    rejected_ball_candidates = int(checkpoint.get("rejectedBallCandidates", 0))
    ball_acceptance_reasons = dict(checkpoint.get("ballAcceptanceReasons", {}))
    ball_rejection_reasons = dict(checkpoint.get("ballRejectionReasons", {}))
    full_ball_detections = int(checkpoint.get("fullBallDetections", 0))
    tiled_ball_detections = int(checkpoint.get("tiledBallDetections", 0))
    frames_with_ball = int(checkpoint.get("framesWithBall", 0))
    max_persons_in_frame = int(checkpoint.get("maxPersonsInFrame", 0))
    person_track_ids = set(checkpoint.get("personTrackIds", []))
    person_tracker_session = int(checkpoint.get("personTrackerSession", 0)) + 1
    person_track_keys = set(checkpoint.get("personTrackKeys", []))
    person_track_creations = int(checkpoint.get("personTrackCreations", 0))
    person_track_associations = int(checkpoint.get("personTrackAssociations", 0))
    person_frames_with_tracks = int(checkpoint.get("personFramesWithTracks", 0))
    person_high_confidence_with_id = int(checkpoint.get("personHighConfidenceWithId", 0))
    person_high_confidence_without_id = int(checkpoint.get("personHighConfidenceWithoutId", 0))
    person_tracked_detections = int(checkpoint.get("personTrackedDetections", 0))
    person_untracked_detections = int(checkpoint.get("personUntrackedDetections", 0))
    person_confidence_sum = float(checkpoint.get("personConfidenceSum", 0.0))
    person_confidence_histogram = list(checkpoint.get("personConfidenceHistogram", [0] * 101))
    if len(person_confidence_histogram) != 101:
        person_confidence_histogram = [0] * 101
    person_confidence_buckets = dict(checkpoint.get("personConfidenceBuckets", {
        "belowTrackLow025": 0, "trackLow025To060": 0,
        "trackHigh060To070": 0, "newTrack070Plus": 0,
    }))
    ball_points = checkpoint.get("ballPoints", [])
    debug_frames = checkpoint.get("debugFrames", [])
    last_debug_timestamp = float(checkpoint.get("lastDebugTimestamp", -1e9))
    tracker = BallTracker()
    tracker.restore(checkpoint.get("ballTrackerTracks", checkpoint.get("ballLinkerTracks", {})))
    tracker.restore_confirmed_ids(checkpoint.get("confirmedBallTrackIds", []))
    tracker.restore_static_ids(checkpoint.get("staticBallTrackIds", []))
    tracker.restore_diagnostics(checkpoint.get("ballTrackerDiagnostics", {}))
    last_timestamp = resume_seconds

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            current_index = frame_index
            frame_index += 1
            timestamp = current_index / fps if fps > 0 else float(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
            last_timestamp = timestamp
            if end_seconds is not None and timestamp >= end_seconds:
                break

            persons_this_frame = 0
            if (current_index - start_frame) % PERSON_FRAME_STRIDE == 0:
                results = person_model.track(
                    frame,
                    persist=True,
                    tracker=PERSON_TRACKER_CONFIG,
                    classes=[0],
                    conf=PERSON_CONFIDENCE,
                    imgsz=PERSON_IMGSZ,
                    verbose=False,
                )
                processed_person_frames += 1
                frame_has_person_track = False
                if results and results[0].boxes is not None:
                    for box in results[0].boxes:
                        if int(box.cls.item()) != 0:
                            continue
                        persons_this_frame += 1
                        person_detections += 1
                        confidence = float(box.conf.item())
                        person_confidence_sum += confidence
                        person_confidence_histogram[min(100, max(0, int(round(confidence * 100))))] += 1
                        if confidence < 0.25:
                            person_confidence_buckets["belowTrackLow025"] += 1
                        elif confidence < 0.60:
                            person_confidence_buckets["trackLow025To060"] += 1
                        elif confidence < 0.70:
                            person_confidence_buckets["trackHigh060To070"] += 1
                        else:
                            person_confidence_buckets["newTrack070Plus"] += 1
                        if box.id is not None:
                            try:
                                track_id = int(box.id.item())
                                person_track_ids.add(track_id)
                                track_key = f"{person_tracker_session}:{track_id}"
                                if track_key in person_track_keys:
                                    person_track_associations += 1
                                else:
                                    person_track_keys.add(track_key)
                                    person_track_creations += 1
                                person_tracked_detections += 1
                                frame_has_person_track = True
                                if confidence >= 0.70:
                                    person_high_confidence_with_id += 1
                            except Exception:
                                person_untracked_detections += 1
                                if confidence >= 0.70:
                                    person_high_confidence_without_id += 1
                        else:
                            person_untracked_detections += 1
                            if confidence >= 0.70:
                                person_high_confidence_without_id += 1
                if frame_has_person_track:
                    person_frames_with_tracks += 1
                max_persons_in_frame = max(max_persons_in_frame, persons_this_frame)

            if (current_index - start_frame) % BALL_FRAME_STRIDE == 0:
                processed_ball_frames += 1
                full_candidates = detect_ball_full(ball_model, frame, timestamp)
                full_ball_detections += len(full_candidates)
                tiled_candidates = []
                if BALL_USE_TILES and (processed_ball_frames % BALL_TILE_STRIDE == 0):
                    tiled_candidates = detect_ball_tiled(ball_model, frame, timestamp)
                    tiled_ball_detections += len(tiled_candidates)

                # Full-frame and tiled inference are independent; fuse their outputs once.
                candidates = merge_ball_candidates(full_candidates + tiled_candidates)
                raw_ball_candidates += len(candidates)
                trackable = [candidate for candidate in candidates
                             if candidate["qualityScore"] >= BALL_TRACK_UPDATE_MIN_SCORE]
                for candidate in candidates:
                    candidate.setdefault("accepted", False)
                    candidate.setdefault("acceptedScore", candidate["qualityScore"])
                    if candidate["qualityScore"] < BALL_TRACK_UPDATE_MIN_SCORE:
                        candidate["rejectionReason"] = "score_below_track_update_threshold"
                rejected_ball_candidates += len(candidates) - len(trackable)
                tracked = tracker.update(trackable, timestamp)
                accepted = [candidate for candidate in tracked if candidate["accepted"]]
                rejected_ball_candidates += len(tracked) - len(accepted)
                rejected = [candidate for candidate in candidates if not candidate["accepted"]]
                for candidate in accepted:
                    reason = candidate.get("acceptanceReason", "accepted")
                    ball_acceptance_reasons[reason] = int(ball_acceptance_reasons.get(reason, 0)) + 1
                for candidate in rejected:
                    reason = candidate.get("rejectionReason", "rejected")
                    ball_rejection_reasons[reason] = int(ball_rejection_reasons.get(reason, 0)) + 1
                accepted_ball_detections += len(accepted)
                if accepted:
                    frames_with_ball += 1
                    remaining = max(0, MAX_BALL_POINTS - len(ball_points))
                    if remaining:
                        ball_points.extend(accepted[:remaining])
                    if (BALL_DEBUG_EXPORT and len(debug_frames) < BALL_DEBUG_MAX_FRAMES
                            and timestamp - last_debug_timestamp >= BALL_DEBUG_MIN_INTERVAL_SECONDS):
                        try:
                            debug_frames.append(export_ball_debug_frame(
                                job_id, frame, timestamp, candidates, accepted, rejected, len(debug_frames) + 1))
                        except Exception as exc:
                            print(f"Debug frame export failed at {timestamp:.3f}s: {exc}", flush=True)
                        last_debug_timestamp = timestamp

            if (processed_ball_frames + processed_person_frames) % 20 == 0:
                pct = min(95, max(2, int(((current_index - start_frame) / range_frames) * 95)))
                state = {
                    "resumeTimestamp": timestamp,
                    "processedPersonFrames": processed_person_frames,
                    "processedBallFrames": processed_ball_frames,
                    "personDetections": person_detections,
                    "pipelineVersion": "CV-02.4",
                    "rawBallCandidates": raw_ball_candidates,
                    "acceptedBallDetections": accepted_ball_detections,
                    "rejectedBallCandidates": rejected_ball_candidates,
                    "ballAcceptanceReasons": ball_acceptance_reasons,
                    "ballRejectionReasons": ball_rejection_reasons,
                    "ballDetections": accepted_ball_detections,
                    "fullBallDetections": full_ball_detections,
                    "tiledBallDetections": tiled_ball_detections,
                    "framesWithBall": frames_with_ball,
                    "maxPersonsInFrame": max_persons_in_frame,
                    "personTrackIds": list(person_track_ids),
                    "personTrackerSession": person_tracker_session,
                    "personTrackKeys": list(person_track_keys),
                    "personTrackCreations": person_track_creations,
                    "personTrackAssociations": person_track_associations,
                    "personFramesWithTracks": person_frames_with_tracks,
                    "personHighConfidenceWithId": person_high_confidence_with_id,
                    "personHighConfidenceWithoutId": person_high_confidence_without_id,
                    "personTrackedDetections": person_tracked_detections,
                    "personUntrackedDetections": person_untracked_detections,
                    "personConfidenceSum": person_confidence_sum,
                    "personConfidenceHistogram": person_confidence_histogram,
                    "personConfidenceBuckets": person_confidence_buckets,
                    "ballPoints": ball_points,
                    "debugFrames": debug_frames,
                    "lastDebugTimestamp": last_debug_timestamp,
                    "ballTrackerTracks": tracker.snapshot(),
                    "confirmedBallTrackIds": sorted(tracker.confirmed_track_ids),
                    "staticBallTrackIds": sorted(tracker.static_track_ids),
                    "ballTrackerDiagnostics": tracker.diagnostics(),
                    "progress": pct,
                }
                status = get_job_status(job_id)
                if status is None:
                    print(f"Analysis {job_id} deleted; stopping worker task", flush=True)
                    return
                save_checkpoint(job_id, state)
                if status == 4:
                    print(f"Analysis {job_id} paused at {timestamp:.2f}s ({pct}%)", flush=True)
                    return
                set_job(job_id, progress=pct)
                print(
                    f"CV02.3 {job_id}: {pct}% t={timestamp:.1f}s persons={person_detections} "
                    f"raw={raw_ball_candidates} accepted={accepted_ball_detections} "
                    f"rejected={rejected_ball_candidates} confirmedTracks={tracker.confirmed_count()}",
                    flush=True,
                )
    finally:
        cap.release()

    unique_ball_tracks = len({p.get("trackId") for p in ball_points if p.get("trackId") is not None})
    accepted_confidences = [float(point["confidence"]) for point in ball_points]
    average_ball_confidence = statistics.fmean(accepted_confidences) if accepted_confidences else 0.0
    median_ball_confidence = statistics.median(accepted_confidences) if accepted_confidences else 0.0
    average_person_confidence = person_confidence_sum / person_detections if person_detections else 0.0
    median_person_confidence = _histogram_median(person_confidence_histogram, person_detections)
    analyzed_seconds = max(0.001, last_timestamp - start_seconds)
    detections_per_second = accepted_ball_detections / analyzed_seconds

    result = {
        "analysisId": str(job_id),
        "gameId": str(game_id),
        "mode": "vision-cv02.4",
        "model": YOLO_MODEL,
        "ballModel": BALL_MODEL,
        "config": {
            "personFrameStride": PERSON_FRAME_STRIDE,
            "personConfidence": PERSON_CONFIDENCE,
            "personImgsz": PERSON_IMGSZ,
            "personTracker": PERSON_TRACKER_CONFIG,
            "personTrackerThresholds": {
                "trackLow": 0.25, "trackHigh": 0.60, "newTrack": 0.70,
                "gmcMethod": "none",
            },
            "ballFrameStride": BALL_FRAME_STRIDE,
            "ballConfidence": BALL_CONFIDENCE,
            "ballImgsz": BALL_IMGSZ,
            "ballUseTiles": BALL_USE_TILES,
            "ballTileStride": BALL_TILE_STRIDE,
            "ballTileImgsz": BALL_TILE_IMGSZ,
            "ballTileOverlap": BALL_TILE_OVERLAP,
            "ballTrackMaxGapSeconds": BALL_TRACK_MAX_GAP_SECONDS,
            "ballTrackBaseDistancePx": BALL_TRACK_BASE_DISTANCE_PX,
            "ballTrackMaxSpeedPxPerSecond": BALL_TRACK_MAX_SPEED_PX_PER_SECOND,
            "ballTrackMinHits": BALL_TRACK_MIN_HITS,
            "ballTrackMaxMisses": BALL_TRACK_MAX_MISSES,
            "ballTrackMaxWeakUpdates": BALL_TRACK_MAX_WEAK_UPDATES,
            "ballAcceptedMinScore": BALL_ACCEPTED_MIN_SCORE,
            "ballTrackUpdateMinScore": BALL_TRACK_UPDATE_MIN_SCORE,
            "ballTrackNewMinScore": BALL_TRACK_NEW_MIN_SCORE,
            "ballTrackNewMinConfidence": BALL_TRACK_NEW_MIN_CONFIDENCE,
            "ballStaticMinHits": BALL_STATIC_MIN_HITS,
            "ballStaticMaxSpeedPxPerSecond": BALL_STATIC_MAX_SPEED_PX_PER_SECOND,
            "ballStaticPenalty": BALL_STATIC_PENALTY,
            "ballDebugExport": BALL_DEBUG_EXPORT,
            "ballDebugMaxFrames": BALL_DEBUG_MAX_FRAMES,
            "ballDebugMinIntervalSeconds": BALL_DEBUG_MIN_INTERVAL_SECONDS,
        },
        "video": {
            "path": video_path,
            "fps": round(fps, 3),
            "totalFrames": total_frames,
            "width": width,
            "height": height,
            "durationSeconds": round(duration, 3),
            "analysisStartSeconds": round(start_seconds, 3),
            "analysisEndSeconds": round(end_seconds, 3) if end_seconds is not None else None,
            "analysisDurationSeconds": round((end_seconds if end_seconds is not None else duration) - start_seconds, 3) if duration > 0 else None,
            "frameStride": PERSON_FRAME_STRIDE,
            "processedFrames": processed_person_frames,
            "processedPersonFrames": processed_person_frames,
            "processedBallFrames": processed_ball_frames,
        },
        "summary": {
            "personDetections": person_detections,
            "rawBallCandidates": raw_ball_candidates,
            "acceptedBallDetections": accepted_ball_detections,
            "rejectedBallCandidates": rejected_ball_candidates,
            "ballAcceptanceReasons": ball_acceptance_reasons,
            "ballRejectionReasons": ball_rejection_reasons,
            "ballDetections": accepted_ball_detections,
            "fullBallDetections": full_ball_detections,
            "tiledBallDetections": tiled_ball_detections,
            "framesWithBall": frames_with_ball,
            "maxPersonsInFrame": max_persons_in_frame,
            "uniquePersonTracks": len(person_track_ids),
            "personTrackCreations": person_track_creations,
            "personTrackAssociations": person_track_associations,
            "personFramesWithTracks": person_frames_with_tracks,
            "personHighConfidenceWithId": person_high_confidence_with_id,
            "personHighConfidenceWithoutId": person_high_confidence_without_id,
            "personTrackedDetections": person_tracked_detections,
            "personUntrackedDetections": person_untracked_detections,
            "averagePersonConfidence": round(average_person_confidence, 4),
            "medianPersonConfidence": round(median_person_confidence, 4),
            "personConfidenceBuckets": person_confidence_buckets,
            "uniqueBallTracks": unique_ball_tracks,
            "confirmedBallTracks": tracker.confirmed_count(),
            "ballTracksCreated": tracker.tracks_created,
            "ballWeakTrackUpdates": tracker.weak_track_updates,
            "validBallTracks": tracker.confirmed_count(),
            "averageBallConfidence": round(average_ball_confidence, 4),
            "medianBallConfidence": round(median_ball_confidence, 4),
            "ballDetectionsPerSecond": round(detections_per_second, 3),
            "storedBallPoints": len(ball_points),
        },
        "ballTrack": ball_points,
        "debugFrames": debug_frames,
    }

    output_path = ANALYSIS_DIR / f"{job_id}.json"
    tmp_path = output_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(output_path)
    delete_checkpoint(job_id)

    set_job(job_id, status=2, progress=100, completed=True)
    print(f"Completed vision CV-02.4 analysis {job_id}; result={output_path}", flush=True)


def process_one():
    claimed = claim_job()
    if not claimed:
        return False

    job_id, game_id, video_path = claimed
    try:
        if ANALYSIS_MODE == "mock":
            process_mock(job_id, game_id)
        else:
            process_vision(job_id, game_id, video_path)
    except Exception as exc:
        message = str(exc)[:2000]
        status = get_job_status(job_id)
        if status is None:
            print(f"Analysis {job_id} was deleted while processing", flush=True)
        elif status == 4:
            print(f"Analysis {job_id} paused", flush=True)
        else:
            print(f"Analysis {job_id} failed: {message}", flush=True)
            set_job(job_id, status=3, progress=0, error=message, completed=True)
    return True


if __name__ == "__main__":
    print(
        f"BasketVision worker CV-02.4 mode={ANALYSIS_MODE} personModel={YOLO_MODEL} ballModel={BALL_MODEL} "
        f"personStride={PERSON_FRAME_STRIDE} ballStride={BALL_FRAME_STRIDE} ballTiles={BALL_USE_TILES}",
        flush=True,
    )
    wait_for_db()
    while True:
        try:
            if not process_one():
                time.sleep(2)
        except Exception as exc:
            print(f"Worker error: {exc}", flush=True)
            time.sleep(3)
