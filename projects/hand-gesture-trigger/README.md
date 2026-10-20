# Hand gesture trigger

Detects a hand from a webcam, classifies the gesture and, when it is stable, fires an action. Gestures: open palm, fist, thumbs up, thumbs down, pointing, peace.

The point is **touchless control**: situations where hands are dirty, wet, gloved or busy and touching a screen is a problem. Typical uses: confirm or reject an item at a counter, advance a recipe step in a kitchen, start a timer, mark an order as ready, control a presentation. Each gesture can POST to a webhook, so it plugs straight into an n8n workflow.

## How it is built

| File | Role |
|---|---|
| `gesture_logic.py` | Pure Python: 21 hand landmarks in, gesture name out, plus a debouncer that ignores flicker. No camera or ML needed, so it is fully unit-tested. |
| `hand_gestures.py` | Thin camera layer: OpenCV capture, MediaPipe hand tracking, on-screen overlay, optional webhook. |

Keeping the decision logic separate from the camera is what makes it testable and easy to tune.

## Run

```bash
pip install -r requirements.txt
python hand_gestures.py                                        # preview
python hand_gestures.py --webhook http://localhost:5678/webhook/gesture
```

The webhook receives `{"gesture": "thumbs_up", "fingers": 1, "ts": 1760000000.0}` once per gesture change.

## Tests

```bash
pip install pytest
pytest
```

The tests build synthetic landmarks for each gesture and for both hands, and check the debouncer.

## Limits

- One hand at a time, palm facing the camera, hand roughly upright.
- Good lighting matters more than camera quality.
- The camera layer is tested by hand, not automatically; the classification logic is automated.
