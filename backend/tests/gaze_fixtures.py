"""Synthetic face landmark sets shared by the gaze tests (T6 / S5).

The numbers are mirrored by ``frontend/src/test/gaze-tracking.test.ts``: the browser and the server must
compute the same gaze features from the same landmarks.
"""
import types

import numpy as np

# Image-left eye (subject's right): corners 33 (outer) / 133 (inner), lids 159 (upper) / 145 (lower).
# Image-right eye (subject's left): corners 362 (inner) / 263 (outer), lids 386 (upper) / 374 (lower).
EYE_WIDTH = 0.06
LEFT_CENTER = (0.43, 0.40)
RIGHT_CENTER = (0.57, 0.40)
LID_OPENING = 0.02


def eye_points(iris_dx=0.0, iris_dy=0.0, opening=LID_OPENING, count=478):
    """478 points: only the eye landmarks matter; ``iris_dx/dy`` move both irises from the eye centers."""
    pts = np.full((count, 3), 0.5, dtype=np.float64)
    for corner_a, corner_b, upper, lower, iris, (cx, cy) in (
        (33, 133, 159, 145, 468, LEFT_CENTER),
        (362, 263, 386, 374, 473, RIGHT_CENTER),
    ):
        pts[corner_a] = (cx - EYE_WIDTH / 2, cy, 0.0)
        pts[corner_b] = (cx + EYE_WIDTH / 2, cy, 0.0)
        pts[upper] = (cx, cy - opening / 2, 0.0)
        pts[lower] = (cx, cy + opening / 2, 0.0)
        pts[iris] = (cx + iris_dx, cy + iris_dy, 0.0)
    return pts


# name -> (iris_dx, iris_dy, expected gaze_h, expected gaze_v) with geometry only (no blendshapes)
GEOMETRY_CASES = {
    "center": (0.0, 0.0, 0.0, 0.0),
    "eyes_right": (0.012, 0.0, 0.8, 0.0),
    "eyes_left": (-0.012, 0.0, -0.8, 0.0),
    "eyes_down": (0.0, 0.006, 0.0, 0.9),
    "eyes_up": (0.0, -0.006, 0.0, -0.9),
}


class FakeCategory:
    def __init__(self, name, score):
        self.category_name, self.score = name, score


def face_result(points, blendshapes=None, matrix=None):
    """A MediaPipe FaceLandmarker result with one face; the head landmarks are a frontal face."""
    pts = np.array(points, dtype=np.float64)
    for index, (x, y, z) in {
        10: (0.5, 0.2, 0.0), 152: (0.5, 0.8, 0.0), 1: (0.5, 0.5, 0.0),
        78: (0.43, 0.65, 0.0), 308: (0.57, 0.65, 0.0), 13: (0.5, 0.64, 0.0), 14: (0.5, 0.66, 0.0),
    }.items():
        pts[index] = (x, y, z)
    landmarks = [types.SimpleNamespace(x=float(p[0]), y=float(p[1]), z=float(p[2])) for p in pts]
    return types.SimpleNamespace(
        face_landmarks=[landmarks],
        face_blendshapes=[[FakeCategory(name, score) for name, score in (blendshapes or {}).items()]],
        facial_transformation_matrixes=[np.eye(4) if matrix is None else matrix],
    )


class FakeLandmarker:
    def __init__(self, result):
        self.result = result

    def detect(self, _image):
        return self.result
