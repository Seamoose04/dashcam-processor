# pipeline/processors/plate_smooth.py
from collections import defaultdict

_global_plate_cache = defaultdict(list)

def load_plate_smoother():
    return None  # no heavy resources

def process_plate_smooth(task, resource):
    """
    task.payload:
      {
         'video_id': '...',
         'car_bbox': [...],
         'plate_bbox': [...],
         'text': 'ABC123',
         'conf': 0.92,
      }
    """
    vid = task.video_id
    key = (vid, tuple(task.payload["car_bbox"]))

    text = task.payload["text"]
    conf = task.payload["conf"]

    if text:
        _global_plate_cache[key].append((text, conf))

    # output "best guess" when enough data accumulated
    guesses = _global_plate_cache[key]
    if len(guesses) < 3:
        return {"final": None}

    # Confidence-weighted voting
    score = {}
    for t, c in guesses:
        score[t] = score.get(t, 0) + c

    best = max(score.items(), key=lambda kv: kv[1])[0]
    return {"final": best}
