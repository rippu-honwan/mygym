"""Rep counter v2 (the tuning twin of WatchCore/RepCounter.swift; keep the two the same).

Velocity along the movement, from the watch's acceleration: a rep is one full swing of it.
  1. userAcceleration (device frame, g) minus its slow mean, integrated with a leak, smoothed:
     a velocity vector that forgets drift.
  2. Its main axis lately (running covariance, one power-iteration step per sample); x = the
     velocity along it.
  3. A swing: x above +th after having been below -th (th follows the recent size of x).
     (`tail`: a still moment as the end of the last rep; off, it counted too much.)
  4. A swing counts when it is like the swings before it in size and period. One that is not
     is ignored; when the swing after a lone first one does not match it, that first one was
     getting into position and its rep is taken back.
"""
import numpy as np

class RepCounter2:
    def __init__(s, hz=50, hp=1.0, leak=0.8, lp=0.12, tau=3.0, k=1.0, floor=0.05, min_pp=0.15,
                 min_period=0.6, lo=0.5, hi=2.2, plo=0.5, phi=2.0, mode="pca", tail=0):
        s.dt = 1.0/hz
        s.hp, s.leak, s.lp, s.tb = s.dt/hp, s.dt/leak, s.dt/lp, s.dt/tau
        s.k, s.floor, s.min_pp, s.min_period, s.lo, s.hi, s.plo, s.phi, s.mode = k, floor, min_pp, min_period, lo, hi, plo, phi, mode
        s.mean = None; s.v = np.zeros(3); s.vs = np.zeros(3)
        s.cov = np.zeros((3, 3)); s.axis = np.array([1.0, 0.0, 0.0]); s.ms = 0.0
        s.state = 0; s.top = 0.0; s.bottom = 0.0; s.last = None; s.quiet = None; s.tail = tail
        s.sizes = []; s.periods = []     # of the swings counted in the current run
        s.odd = None                     # a swing that did not fit: (size, period)
        s.reps = 0; s.events = []
    def push(s, t, a, g):
        a = np.asarray(a, float)*9.81
        if s.mode == "vert":
            g = np.asarray(g, float); a = np.array([a@g/np.linalg.norm(g), 0.0, 0.0])
        if s.mean is None: s.mean = a
        s.mean = s.mean + (a - s.mean)*s.hp
        s.v = s.v + (a - s.mean)*s.dt
        s.v = s.v - s.v*s.leak
        s.vs = s.vs + (s.v - s.vs)*s.lp
        s.cov = s.cov + (np.outer(s.vs, s.vs) - s.cov)*s.tb
        n = s.cov@s.axis; nn = np.linalg.norm(n)
        if nn > 0: s.axis = n/nn
        x = float(s.vs@s.axis)
        s.ms = s.ms + (x*x - s.ms)*s.tb
        th = max(s.floor, s.k*s.ms**0.5)
        s.top = max(s.top, x); s.bottom = min(s.bottom, x)
        if abs(x) > th: s.quiet = t
        if x < -th and s.state >= 0:
            s.state = -1
        elif s.state <= 0 and (x > th or (s.state < 0 and s.tail and s.quiet is not None and t - s.quiet >= s.tail)):
            # Up again after having been down: one swing. Or down and then still for a moment:
            # the last rep of the set, which nothing follows.
            was = s.state; s.state = 1 if x > th else 0
            if was < 0:
                period = None if s.last is None else t - s.last
                if period is None or period >= s.min_period:
                    s._swing(s.top - s.bottom, period, t); s.last = t
                    s.top = max(x, 0.0); s.bottom = 0.0
            else:
                s.top = x; s.bottom = 0.0
        return s.reps
    @staticmethod
    def _like(size, period, sizes, periods, lo, hi, plo, phi):
        m = float(np.median(sizes[-5:]))
        if not (lo*m <= size <= hi*m): return False
        if period is None or not periods: return True
        p = float(np.median(periods[-5:]))
        return plo*p <= period <= phi*p
    def _swing(s, size, period, t):
        if size < s.min_pp: return
        if not s.sizes:
            s.sizes = [size]; s.periods = []; s.reps += 1; s.events.append(t); return
        if s._like(size, period, s.sizes, s.periods, s.lo, s.hi, s.plo, s.phi):
            s.sizes.append(size); s.odd = None
            if period is not None: s.periods.append(period)
            s.reps += 1; s.events.append(t); return
        if len(s.sizes) == 1:
            # the lone first swing was getting into position: this one starts the count
            s.sizes = [size]; s.periods = []; s.odd = None; s.events[-1] = t; return
        if s.odd is not None and s._like(size, None, [s.odd[0]], [], s.lo, s.hi, s.plo, s.phi):
            # two alike in a row that are not like the reps before: the reps changed, both count
            s.sizes = [s.odd[0], size]; s.periods = [period] if period else []; s.odd = None
            s.reps += 2; s.events += [t, t]; return
        s.odd = (size, period)

def run(t, a, g, **kw):
    c = RepCounter2(**kw)
    for i in range(len(t)): c.push(t[i], a[i], g[i])
    return c

def fused(t, a, g, **kw):
    """What the watch counts (MotionRecorder): the larger of the speed and the tilt counter.
    Speed misses slow reps (they barely accelerate), tilt misses reps that hardly turn the wrist."""
    from tilt import run as tilt
    return max(run(t, a, g, **kw).reps, tilt(t, g).reps)

if __name__ == "__main__":
    import glob, os, sys, json
    D = os.path.expanduser("~/dev/mygym/data/motion/" + os.environ["MYGYM_UID"])
    # reps the user logged (gym, not all certain) or told (home, certain)
    GYM = {"141135_0577_s1":10,"141808_0577_s3":7,"142614_0025_s2":8,"144741_0334_s1":12,"145108_0334_s2":12,
           "145417_0031_s1":12,"150745_1323_s1":10,"151015_1323_s2":10,"151308_1323_s3":16,
           "152109_0194_s1":10,"152405_0194_s2":8,"152720_0194_s3":6}
    HOME = {"224519_0025_s1":10,"224735_0025_s2":10,"224809_0025_s3":10,"224910_0031_s1":10}
    JUNK = {"141458_0577_s2":11,"143627_0047_s1":8,"144103_0047_s2":10,"142947_0025_s3":8,"150209_0031_s3":6,"151731_2330_s1":6}
    kw = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    for name, T in (("home", HOME), ("gym", GYM), ("gaps/junk", JUNK)):
        out = []; tot = 0
        for k, tr in T.items():
            x = np.genfromtxt(glob.glob(f"{D}/*{k}.csv")[0], delimiter=",", skip_header=2)
            e = fused(x[:,0], x[:,1:4], x[:,7:10], **kw) - tr; out.append(f"{e:+d}"); tot += abs(e)
        print(f"{name:10s} abs {tot:3d} | " + " ".join(out))
