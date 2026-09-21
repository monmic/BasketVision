"""Conservative frame-to-frame camera motion; unreliable fits return no evidence."""
import cv2
import numpy as np


class CameraMotion:
    def __init__(self):
        self.previous = None
        self.timestamp = None

    def update(self, frame, timestamp):
        height, width = frame.shape[:2]
        scale = min(1.0, 640 / width)
        gray = cv2.cvtColor(cv2.resize(frame, (round(width * scale), round(height * scale))), cv2.COLOR_BGR2GRAY)
        previous, previous_time = self.previous, self.timestamp
        self.previous, self.timestamp = gray, timestamp
        if (previous is None or previous.shape != gray.shape
                or not 0 < timestamp - previous_time <= .25):
            return None
        points = cv2.goodFeaturesToTrack(previous, maxCorners=300, qualityLevel=.02, minDistance=8)
        if points is None or len(points) < 30:
            return None
        tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous, gray, points, None)
        if tracked is None:
            return None
        back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, previous, tracked, None)
        if back is None:
            return None
        good = (status.ravel() == 1) & (back_status.ravel() == 1) & (np.linalg.norm(back-points, axis=2).ravel() < 1)
        a, b = points[good].reshape(-1, 2), tracked[good].reshape(-1, 2)
        if len(a) < 25:
            return None
        matrix, mask = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2)
        if matrix is None or not np.isfinite(matrix).all():
            return None
        inliers = a[mask.ravel() == 1]
        ratio = len(inliers) / len(a)
        if len(inliers) < 30 or ratio < .5:
            return None
        # A moving player must not supply the entire camera estimate.
        if np.ptp(inliers[:, 0]) < gray.shape[1] * .5 or np.ptp(inliers[:, 1]) < gray.shape[0] * .35:
            return None
        cells = {(min(3, int(x * 4 / gray.shape[1])), min(2, int(y * 3 / gray.shape[0]))) for x, y in inliers}
        if len(cells) < 6 or not .9 <= np.hypot(matrix[0, 0], matrix[1, 0]) <= 1.1:
            return None
        matrix[:, 2] /= scale
        return {"fromTimestamp": previous_time, "toTimestamp": timestamp,
                "matrix": matrix.tolist(), "inlierRatio": round(ratio, 4), "inliers": len(inliers)}
