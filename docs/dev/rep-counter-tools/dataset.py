"""The sets to tune a rep counter on: every set file that the watch recorded with its log
(from 2026-11-13), with the reps the user left at Done (crown-corrected, or accepted as counted)
as the truth. One file per set (the newest of a set done again). Used by counter3.py.

    from dataset import sets
    for s in sets(): s["t"], s["acc"], s["rot"], s["grav"], s["reps"], s["checked"], s["name"]
"""
import glob, json, os
import numpy as np

DATA = os.environ.get("MYGYM_DATA", os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))


def sets(min_seconds=3):
    latest = {}
    for f in glob.glob(os.path.join(DATA, "motion", "*", "*.csv")):
        if "_synclog_" in f or "_watchlog_" in f or "_hr_" in f:
            continue
        with open(f, encoding="utf-8") as fh:
            meta = json.loads(fh.readline()[2:])
        if meta.get("kind") or meta.get("reps") is None or not (meta.get("helpers") or {}).get("log"):
            continue
        key = (meta.get("wid"), meta.get("exId"), meta.get("set"), meta.get("side"))
        if key not in latest or latest[key][0]["end"] < meta["end"]:
            latest[key] = (meta, f)
    out = []
    for meta, f in latest.values():
        a = np.genfromtxt(f, delimiter=",", skip_header=2)
        if a.ndim < 2 or a[-1, 0] < min_seconds:
            continue
        out.append({"name": os.path.basename(f)[:-4], "t": a[:, 0], "acc": a[:, 1:4], "rot": a[:, 4:7],
                    "grav": a[:, 7:10], "reps": int(round(meta["reps"])), "auto": meta.get("auto"),
                    "checked": bool(meta.get("checked")) or any(str(l[1]).startswith("edit") for l in meta["helpers"]["log"]),
                    "goal": meta.get("goal"), "meta": meta})
    return sorted(out, key=lambda s: s["name"])


if __name__ == "__main__":
    S = sets()
    d = np.array([s["auto"] - s["reps"] for s in S])
    print(len(S), "sets,", sum(s["checked"] for s in S), "checked by hand")
    print(f"watch at the time: exact {np.mean(d == 0) * 100:.0f}%, within 1 {np.mean(np.abs(d) <= 1) * 100:.0f}%, mean abs {np.abs(d).mean():.2f}")
