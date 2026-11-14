import Foundation

/*
 * Rep counter v3 (docs/dev/rep-counter.md): which of the two counters' reps count, one event at a
 * time. Twin: docs/dev/rep-counter-tools/counter3.py (keep the two the same).
 *
 *   1. Speed first (RepCounter). The tilt counter's (TiltCounter) reps count instead only once it
 *      has 5 and the speed counter under 0.6 times as many: a slow or wrist-turning movement.
 *      v2 took the larger of the two and so added both counters' extra reps.
 *   2. A rep within max(0.8 s, 0.35 x the median gap, from 3 gaps on) of the one before is the
 *      same rep (RepGate).
 *   3. The ends of a set: from 4 reps on, one that comes over 1.8 x the median gap after the one
 *      before waits, and counts only when the next one follows at a normal gap (else it was
 *      re-racking). At 5 reps, a first rep that stood 1.8 x the median gap before the second is
 *      taken back (getting into position).
 * Replay on 44 sets with the reps left at Done: within one 50 % -> 61 %, exact 30 % -> 32 %, mean
 * error 2.18 -> 1.73; on the 29 corrected by hand: within one 31 % -> 52 %, exact 0 % -> 28 %.
 */
struct RepFusion {
    // ponytail: tuned on two workouts (2026-11-13/14); re-tune with counter3.py as sets add up.
    static let minGap = 0.8, relGap = 0.35, apart = 1.8, tiltRatio = 0.6, minTilt = 5

    private(set) var speed: [Double] = [], tilt: [Double] = []
    private(set) var source = "speed"
    /// The reps counted, by time.
    private(set) var times: [Double] = []
    private var pending: Double?
    var count: Int { times.count }

    /// The median as numpy has it (the mean of the two middle values of an even count): the
    /// tuning script and this must agree on every gap.
    private static func median<S: Sequence>(_ values: S) -> Double where S.Element == Double {
        let v = values.sorted()
        guard !v.isEmpty else { return 0 }
        return v.count % 2 == 1 ? v[v.count / 2] : (v[v.count / 2 - 1] + v[v.count / 2]) / 2
    }
    private var medianGap: Double { RepFusion.median(zip(times.dropFirst(), times).map { $0 - $1 }) }

    /// A rep from one counter ("speed" or "tilt") at t. Returns how the count changed (it can go
    /// down: a first rep taken back, or the switch to the tilt counter).
    @discardableResult
    mutating func event(t: Double, from counter: String) -> Int {
        if counter == "speed" { speed.append(t) } else { tilt.append(t) }
        let before = count
        if source == "speed", tilt.count >= RepFusion.minTilt, Double(speed.count) < RepFusion.tiltRatio * Double(tilt.count) {
            source = "tilt"
            let old = tilt.dropLast()
            times = []; pending = nil
            for x in old { admit(x) }
        }
        if counter == source { admit(t) }
        return count - before
    }

    private mutating func admit(_ t: Double) {
        // the relative part only from 3 gaps on: an early setup move must not set the pace
        if let last = times.last, t - last < max(RepFusion.minGap, times.count >= 4 ? RepFusion.relGap * medianGap : 0) { return }
        if let p = pending {
            if t - p <= RepFusion.apart * medianGap { times.append(p) }
            pending = nil
        }
        if times.count >= 4, let last = times.last, t - last > RepFusion.apart * medianGap {
            pending = t
            return
        }
        times.append(t)
        if times.count == 5 {
            let g = zip(times.dropFirst(), times).map { $0 - $1 }
            if g[0] > RepFusion.apart * RepFusion.median(g.dropFirst()) { times.removeFirst() }
        }
    }
}
