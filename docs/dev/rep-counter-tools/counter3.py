"""Rep counter v3: the tuning twin of WatchCore/RepFusion.swift (keep the two the same).

The speed counter (counter2.RepCounter2) and the tilt counter (tilt.RepCounter) run as before;
v3 decides which reps count, one event at a time:
  1. Speed first. The tilt counter's reps count instead only when, from its 5th rep, the speed
     counter has seen under 0.6 times as many (a slow or wrist-turning movement: lateral raise, face
     pull). Taking the larger of the two (v2) added both counters' extra reps.
  2. RepGate: a rep within max(0.8 s, 0.35 x the median gap; the latter from 3 gaps on) of the
     one before is the same rep.
  3. The ends: from 3 gaps on, a rep that comes more than 1.8 x the median gap after the one
     before waits; the next rep at a normal gap confirms it (both count), otherwise it never
     counts (re-racking, reaching for the phone). Once 4 reps are in, a first rep that stood
     1.8 x the median gap before the second is taken back (getting into position).
Replayed on the 44 sets with the reps left at Done (2026-11-13/14), against v2 as the watch ran it:
  all 44:          within one 50 % -> 61 %, exact 30 % -> 32 %, mean error 2.18 -> 1.73
  29 hand-checked: within one 31 % -> 52 %, exact  0 % -> 28 %, mean error 2.76 -> 1.79
(The offline best, trimming both ends after the set, reached 66 % / 28 % / 1.62 on the checked
sets; a live count cannot see the end of the set in advance.)
"""
import numpy as np
from counter2 import RepCounter2
from tilt import RepCounter as Tilt


class RepFusion:
    MIN_GAP, REL_GAP, APART, TILT_RATIO, MIN_TILT = 0.8, 0.35, 1.8, 0.6, 5

    def __init__(s):
        s.speed, s.tilt = [], []          # each counter's raw rep times
        s.use = "speed"
        s.times = []                      # reps counted
        s.pending = None                  # a rep after a long gap, not counted yet
        s.count = 0

    def _median_gap(s):
        g = np.diff(s.times)
        return float(np.median(g)) if len(g) else 0.0

    def _source(s):
        if s.use == "speed" and len(s.tilt) >= s.MIN_TILT and len(s.speed) < s.TILT_RATIO * len(s.tilt):
            s.use = "tilt"
            return True
        return False

    def event(s, t, source):
        """A rep from one counter ("speed" or "tilt") at t. Returns the change of the count."""
        (s.speed if source == "speed" else s.tilt).append(t)
        before = s.count
        if s._source():
            # switched to the tilt counter: its reps so far, through the same rules
            old = s.tilt[:-1]
            s.times, s.pending, s.count = [], None, 0
            for x in old:
                s._admit(x)
        if source == s.use:
            s._admit(t)
        return s.count - before

    def _admit(s, t):
        if s.times:
            # the relative part only from 3 gaps on: an early setup move must not set the pace
            med = s._median_gap() if len(s.times) >= 4 else 0.0
            if t - s.times[-1] < max(s.MIN_GAP, s.REL_GAP * med):
                return
        if s.pending is not None:
            # the rep after a long gap was a rep if this one comes at a normal gap after it
            med = s._median_gap()
            if t - s.pending <= s.APART * med:
                s.times.append(s.pending); s.count += 1
            s.pending = None
        if len(s.times) >= 4 and t - s.times[-1] > s.APART * s._median_gap():
            s.pending = t
            return
        s.times.append(t); s.count += 1
        # a first rep that stood apart from the run: getting into position
        if len(s.times) == 5:
            g = np.diff(s.times)
            if g[0] > s.APART * float(np.median(g[1:])):
                s.times.pop(0); s.count -= 1


def run(t, acc, grav):
    c, tl, f = RepCounter2(), Tilt(), RepFusion()
    for i in range(len(t)):
        v0, t0 = c.reps, tl.reps
        c.push(t[i], acc[i], grav[i]); tl.push(t[i], grav[i])
        for _ in range(c.reps - v0): f.event(t[i], "speed")
        for _ in range(tl.reps - t0): f.event(t[i], "tilt")
    return f


if __name__ == "__main__":
    from dataset import sets
    S = sets()
    for label, sel in (("all", lambda s: True), ("checked", lambda s: s["checked"])):
        d = np.array([run(s["t"], s["acc"], s["grav"]).count - s["reps"] for s in S if sel(s)])
        v = np.array([s["auto"] - s["reps"] for s in S if sel(s)])
        print(f"{label:8s} n={len(d):2d} | v3 exact {np.mean(d==0)*100:3.0f}% within1 {np.mean(abs(d)<=1)*100:3.0f}% mae {abs(d).mean():.2f} bias {d.mean():+.2f}"
              f" | v2 as run exact {np.mean(v==0)*100:3.0f}% within1 {np.mean(abs(v)<=1)*100:3.0f}% mae {abs(v).mean():.2f}")
