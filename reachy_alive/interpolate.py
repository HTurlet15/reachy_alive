# reachy_alive/moves/interpolation.py
"""Functions that shape how a value travels between two poses."""

def interpolate(start: float, end: float, p: float) -> float:
    """Return the value p of the way from start to end (p=0 -> start, p=1 -> end)."""
    return start + (end - start) * p