"""Webcam hand-gesture trigger.

Detects one hand with MediaPipe, classifies the gesture (see gesture_logic.py)
and, once a gesture is stable, optionally POSTs it to a webhook (for example an
n8n Webhook node).

    python hand_gestures.py                       # preview only
    python hand_gestures.py --webhook http://localhost:5678/webhook/gesture
    python hand_gestures.py --camera 1 --frames 10

Press q or Esc to quit.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

import cv2
import mediapipe as mp

from gesture_logic import Debouncer, classify, count_fingers


def post_webhook(url: str, gesture: str, fingers: int) -> None:
    body = json.dumps({"gesture": gesture, "fingers": fingers, "ts": time.time()}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3):
            pass
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"webhook failed: {exc}", file=sys.stderr)


def run(camera: int, webhook: str | None, frames: int) -> int:
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        print(f"Could not open camera {camera}", file=sys.stderr)
        return 1
    hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.8,
                                     min_tracking_confidence=0.6)
    drawing = mp.solutions.drawing_utils
    debounce = Debouncer(frames)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # mirror, so "Left"/"Right" match the viewer
            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            gesture, fingers = None, 0
            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0]
                side = result.multi_handedness[0].classification[0].label
                pts = [(p.x, p.y) for p in lm.landmark]
                gesture, fingers = classify(pts, side), count_fingers(pts, side)
                drawing.draw_landmarks(frame, lm, mp.solutions.hands.HAND_CONNECTIONS)
            confirmed = debounce.update(gesture)
            if confirmed:
                print(f"gesture: {confirmed}")
                if webhook:
                    post_webhook(webhook, confirmed, fingers)
            label = f"{gesture or '-'}  fingers: {fingers}"
            cv2.putText(frame, label, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Hand gesture trigger", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        hands.close()
        cap.release()
        cv2.destroyAllWindows()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Detect hand gestures from a webcam.")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--webhook", help="URL that receives a JSON POST on each new gesture")
    ap.add_argument("--frames", type=int, default=8, help="Frames a gesture must hold")
    a = ap.parse_args(argv)
    return run(a.camera, a.webhook, a.frames)


if __name__ == "__main__":
    raise SystemExit(main())
