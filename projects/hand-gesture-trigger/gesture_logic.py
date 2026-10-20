"""Pure gesture logic: landmarks in, gesture name out. No camera or ML needed.

Landmarks follow MediaPipe Hands: 21 points, each with normalized x, y
(origin top-left, y grows downward). Index reference:
    0 wrist | 4 thumb tip | 8 index tip | 12 middle tip | 16 ring tip | 20 pinky tip
A finger is "up" when its tip is above its PIP joint (smaller y).
"""
from __future__ import annotations

from typing import Sequence, Tuple

Point = Tuple[float, float]

FINGER_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
FINGER_PIPS = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}
THUMB_TIP, THUMB_IP, THUMB_MCP = 4, 3, 2


def fingers_up(landmarks: Sequence[Point], handedness: str = "Right") -> dict[str, bool]:
    """Return which fingers are extended. ``handedness`` is "Left" or "Right"
    as reported for a mirrored (selfie) image."""
    if len(landmarks) != 21:
        raise ValueError("Expected 21 landmarks")
    up = {name: landmarks[FINGER_TIPS[name]][1] < landmarks[FINGER_PIPS[name]][1]
          for name in FINGER_TIPS}
    # The thumb moves sideways, so compare x instead of y.
    tip_x, ip_x = landmarks[THUMB_TIP][0], landmarks[THUMB_IP][0]
    up["thumb"] = tip_x > ip_x if handedness == "Left" else tip_x < ip_x
    return up


def count_fingers(landmarks: Sequence[Point], handedness: str = "Right") -> int:
    return sum(fingers_up(landmarks, handedness).values())


def classify(landmarks: Sequence[Point], handedness: str = "Right") -> str:
    """Map finger states to a gesture name."""
    f = fingers_up(landmarks, handedness)
    others = [f["index"], f["middle"], f["ring"], f["pinky"]]
    if all(f.values()):
        return "open_palm"
    if not any(f.values()):
        return "fist"
    if f["thumb"] and not any(others):
        # Thumbs up vs down: is the thumb tip above the wrist?
        return "thumbs_up" if landmarks[THUMB_TIP][1] < landmarks[0][1] else "thumbs_down"
    if f["index"] and not f["middle"] and not f["ring"] and not f["pinky"]:
        return "pointing"
    if f["index"] and f["middle"] and not f["ring"] and not f["pinky"]:
        return "peace"
    return "unknown"


class Debouncer:
    """Only report a gesture once it has been stable for ``frames`` frames,
    and only when it changes. Avoids firing actions on flickering detections."""

    def __init__(self, frames: int = 8):
        self.frames = frames
        self._candidate = None
        self._count = 0
        self._reported = None

    def update(self, gesture: str | None) -> str | None:
        if gesture != self._candidate:
            self._candidate, self._count = gesture, 1
        else:
            self._count += 1
        if self._count >= self.frames and gesture != self._reported:
            self._reported = gesture
            return gesture
        return None
