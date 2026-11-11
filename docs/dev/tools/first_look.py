"""First look at one gym session: naive rep count per set vs the reps on the server.

Not the Phase 4 algorithm. Two candidate signals per set, both band-passed 0.15-1.5 Hz:
  tilt: first principal component of the gravity vector (how the wrist turns)
  vert: user acceleration along gravity (up/down push)
Reps = peaks with prominence >= 0.35 x the signal's 5-95 % range, at least 1 s apart.
usage: first_look.py <state.json> <workout id> <out.png> <csv...>
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

HZ = 50
state, wid, out, paths = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
s = json.load(open(state))
s = s.get("state", s)
workout = next(w for w in s["workouts"] if w["id"] == wid)
truth = {(e["id"], i + 1): st.get("r") for e in workout["entries"] for i, st in enumerate(e["sets"])}


def count(x):
    b, a = butter(2, [0.15 / (HZ / 2), 1.5 / (HZ / 2)], btype="band")
    y = filtfilt(b, a, x)
    span = np.percentile(y, 95) - np.percentile(y, 5)
    up, _ = find_peaks(y, prominence=0.35 * span, distance=HZ)
    return y, up


rows = []
fig, axes = plt.subplots(len(paths), 1, figsize=(10, 1.9 * len(paths)), squeeze=False)
for ax, path in zip(axes[:, 0], paths):
    meta = json.loads(open(path).readline()[2:])
    d = np.genfromtxt(path, delimiter=",", skip_header=2)
    if d.ndim == 1 or len(d) < HZ * 5:
        rows.append((os.path.basename(path)[9:15], meta["name"].split("(")[-1].rstrip(")")[:34], meta["set"], "short", "", "", ""))
        ax.set_title(f"{rows[-1][1]} set {meta['set']}: too short", fontsize=9)
        continue
    t = np.arange(0, d[-1, 0], 1 / HZ)                       # uniform grid: gaps become straight lines
    acc = np.c_[[np.interp(t, d[:, 0], d[:, i]) for i in (1, 2, 3)]].T
    grav = np.c_[[np.interp(t, d[:, 0], d[:, i]) for i in (7, 8, 9)]].T
    g0 = grav - grav.mean(axis=0)
    tilt = g0 @ np.linalg.svd(g0, full_matrices=False)[2][0]
    vert = -(acc * grav).sum(axis=1)
    yt, pt = count(tilt)
    yv, pv = count(vert)
    real = truth.get((meta["exId"], meta["set"]))
    rows.append((os.path.basename(path)[9:15], meta["name"].split("(")[-1].rstrip(")")[:34], meta["set"],
                 real, len(pt), len(pv), f"{t[-1]:.0f}s"))
    ax.plot(t, yt / (np.abs(yt).max() or 1), lw=1.2, label="tilt")
    ax.plot(t[pt], (yt / (np.abs(yt).max() or 1))[pt], "rx", ms=7)
    ax.plot(t, yv / (np.abs(yv).max() or 1) - 2.2, lw=1.0, color="gray", label="vert")
    ax.set_yticks([])
    ax.set_title(f"{rows[-1][1]} set {meta['set']}: real {real}, tilt {len(pt)}, vert {len(pv)}", fontsize=9)
fig.tight_layout()
fig.savefig(out, dpi=90)

print(f"{'time':7}{'exercise':36}{'set':>4}{'real':>6}{'tilt':>6}{'vert':>6}{'len':>7}")
for r in rows:
    print(f"{r[0]:7}{r[1]:36}{r[2]!s:>4}{r[3]!s:>6}{r[4]!s:>6}{r[5]!s:>6}{r[6]:>7}")
ok = [r for r in rows if isinstance(r[3], int) and isinstance(r[4], int)]
print("tilt exact", sum(r[3] == r[4] for r in ok), "within 1", sum(abs(r[3] - r[4]) <= 1 for r in ok), "of", len(ok))
print("vert exact", sum(r[3] == r[5] for r in ok), "within 1", sum(abs(r[3] - r[5]) <= 1 for r in ok), "of", len(ok))
