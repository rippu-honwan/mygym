"""Streaming rep counter on the gravity vector (the wrist's orientation), v2.
The smoothed vector zigzags between two orientations; each reversal is a turning point.
A turning point that comes back to where the one before last was (same end of the
movement) proves one half of a rep; two halves are one rep."""
import numpy as np

class RepCounter:
    def __init__(s, hz=50, smooth=0.12, tau=1.5, back=1.2, min_back=0.04, min_amp=0.1,
                 near=1.0, min_seg=0.25, max_seg=6.0, keep=0, dwell=0, anchor=1, keepbad=0):
        s.dt = 1.0/hz; s.a = s.dt/smooth; s.b = s.dt/tau
        s.back, s.min_back, s.min_amp, s.near, s.min_seg, s.max_seg, s.keep = back, min_back, min_amp, near, min_seg, max_seg, keep
        s.run_half = 0; s.dwell = dwell; s.anchor = anchor; s.keepbad = keepbad
        s.g = None; s.m = None; s.v = 0.0
        s.E = None; s.P = None; s.dmax = 0.0; s.tE = 0.0; s.tP = 0.0
        s.pts = []          # last turning points: (P, amp of the segment that ended there)
        s.run = 0           # turning points in a row that came back to their place
        s.half = 0; s.reps = 0; s.events = []; s.log = []
    def push(s, t, g):
        g = np.asarray(g, float)
        if s.g is None:
            s.g = g; s.E = g; s.P = g; s.m = g; s.tE = s.tP = t
            if s.anchor: s.pts = [(g, 0.0)]
            return 0
        s.g = s.g + (g - s.g)*s.a
        # how much the wrist moves lately: the scale a reversal is measured against
        s.m = s.m + (s.g - s.m)*s.b
        s.v = s.v + (float(np.sum((s.g - s.m)**2)) - s.v)*s.b
        d = np.linalg.norm(s.g - s.E)
        if d > s.dmax:
            s.dmax = d; s.P = s.g; s.tP = t
        elif np.linalg.norm(s.g - s.P) >= max(s.min_back, s.back*s.v**0.5) or (s.dwell and s.dmax >= s.min_amp and t - s.tP >= s.dwell):
            new = s._turn(s.P, s.dmax, s.tP - s.tE, t)
            s.E = s.P; s.tE = s.tP
            s.dmax = np.linalg.norm(s.g - s.E); s.P = s.g; s.tP = t
            return new
        return 0
    def _turn(s, P, amp, dur, now):
        before = s.reps
        ok = amp >= s.min_amp and s.min_seg <= dur <= s.max_seg
        back = False
        if ok and len(s.pts) >= 2:
            P2, _ = s.pts[-2]; _, amp1 = s.pts[-1]
            back = amp1 > 0 and np.linalg.norm(P - P2) <= s.near*min(amp, amp1) and 0.5 <= amp/amp1 <= 2.0
        s.log.append((round(float(now), 1), round(float(amp), 2), round(float(dur), 2), int(back)))
        if back:
            s.run += 1
            # the first return proves the two segments behind it as well
            add = 2 if s.run == 1 else 1
            s.half += add; s.run_half += add
        else:
            # a short run was not the exercise (getting into position): its reps go again
            if 0 < s.run < s.keep: s.half -= s.run_half
            s.run = 0; s.run_half = 0
        s.pts = (s.pts + [(P, amp)])[-2:] if ok else ([(P, 0.0)] if s.keepbad else [])
        s.reps = s.half // 2
        if s.reps > before: s.events.append(now)
        return s.reps - before

def run(t, g, **kw):
    c = RepCounter(**kw)
    for ti, gi in zip(t, g): c.push(ti, gi)
    return c
