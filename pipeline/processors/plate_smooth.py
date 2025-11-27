from collections import defaultdict
from difflib import SequenceMatcher

_global_plate_cache = defaultdict(list)

def load_plate_smoother():
    return None  # no resources to load


def _similarity(a: str, b: str) -> float:
    """Character-level similarity score between 0 and 1."""
    return SequenceMatcher(None, a, b).ratio()


def _merge_strings(strings):
    """Merge similar strings into a consensus."""
    if len(strings) == 1:
        return strings[0][0]

    # Weighted combine by confidence
    weighted = []
    for s, c in strings:
        weighted.append((s, c))

    # Find base candidate = string with highest cumulative similarity to others
    best_base = None
    best_score = -1

    for base, _ in weighted:
        total = 0.0
        for s, c in weighted:
            total += _similarity(base, s) * c
        if total > best_score:
            best_score = total
            best_base = base

    # Now refine by voting for each character position
    consensus = list(best_base)

    # Allow merging strings of different lengths meaningfully
    max_len = max(len(s) for s, _ in weighted)
    expanded = []
    for s, c in weighted:
        # pad to max_len
        padded = s.ljust(max_len)
        expanded.append((padded, c))

    final_chars = []
    for i in range(max_len):
        votes = defaultdict(float)
        for s, c in expanded:
            char = s[i]
            votes[char] += c
        best_char = max(votes.items(), key=lambda kv: kv[1])[0]
        final_chars.append(best_char)

    return "".join(final_chars).strip()


def process_plate_smooth(task, resource):
    """
    task.meta fields we use:
      - 'text'
      - 'conf'
      - 'car_bbox'
      - 'plate_bbox'

    We group by (video_id, track_id).
    """
    vid = task.video_id
    tid = task.track_id  # MUCH more stable than bbox

    # OCR data arrives in the task payload; prefer that over meta.
    text = None
    conf = None
    if isinstance(task.payload, dict):
        text = task.payload.get("text")
        conf = task.payload.get("conf")
    # Fallback for any legacy callers that still set meta.
    if text is None:
        text = task.meta.get("text")
    if conf is None:
        conf = task.meta.get("conf")

    key = (vid, tid)

    if text:
        _global_plate_cache[key].append((text, conf))

    guesses = _global_plate_cache[key]

    # If we have 2+ samples, try to generate a stable final
    if len(guesses) >= 2:
        final_guess = _merge_strings(guesses)
        return {"final": final_guess, "conf": max(c for _, c in guesses)}

    # Not enough observations yet
    return {"final": None}
