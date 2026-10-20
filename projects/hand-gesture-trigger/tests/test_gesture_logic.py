import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gesture_logic as g  # noqa: E402


def hand(thumb=False, index=False, middle=False, ring=False, pinky=False,
         handedness="Right", thumb_down=False):
    """Build synthetic landmarks. Fingers 'up' have the tip above the PIP joint."""
    pts = [(0.5, 0.9)] * 21
    pts = list(pts)
    pts[0] = (0.5, 0.9)  # wrist
    for name, up in (("index", index), ("middle", middle), ("ring", ring), ("pinky", pinky)):
        tip, pip = g.FINGER_TIPS[name], g.FINGER_PIPS[name]
        pts[pip] = (0.5, 0.5)
        pts[tip] = (0.5, 0.3 if up else 0.7)
    # Thumb: extended means the tip is further out than the IP joint.
    pts[g.THUMB_IP] = (0.5, 0.6)
    outward = -0.1 if handedness == "Right" else 0.1
    pts[g.THUMB_TIP] = (0.5 + (outward if thumb else -outward),
                        1.0 if thumb_down else (0.4 if thumb else 0.6))
    return pts


@pytest.mark.parametrize("kwargs,expected", [
    (dict(thumb=True, index=True, middle=True, ring=True, pinky=True), "open_palm"),
    (dict(), "fist"),
    (dict(thumb=True), "thumbs_up"),
    (dict(thumb=True, thumb_down=True), "thumbs_down"),
    (dict(index=True), "pointing"),
    (dict(index=True, middle=True), "peace"),
    (dict(index=True, pinky=True), "unknown"),
])
@pytest.mark.parametrize("handedness", ["Right", "Left"])
def test_classify(kwargs, expected, handedness):
    assert g.classify(hand(handedness=handedness, **kwargs), handedness) == expected


def test_count_fingers():
    assert g.count_fingers(hand(index=True, middle=True, ring=True)) == 3
    assert g.count_fingers(hand()) == 0


def test_wrong_landmark_count():
    with pytest.raises(ValueError):
        g.fingers_up([(0, 0)] * 5)


def test_debouncer_requires_stability_and_reports_once():
    d = g.Debouncer(frames=3)
    out = [d.update("fist") for _ in range(5)]
    assert out == [None, None, "fist", None, None]
    assert [d.update("peace") for _ in range(3)] == [None, None, "peace"]


def test_debouncer_ignores_flicker():
    d = g.Debouncer(frames=3)
    seq = ["fist", "peace", "fist", "peace", "fist"]
    assert all(d.update(x) is None for x in seq)
