import Foundation

/*
 * What the speed of a set's reps says (docs/dev/rep-counter.md), from RepCounter's repSizes and
 * repTimes. Speeds are relative: the watch integrates its own acceleration on one wrist.
 */
enum SetSpeed {
    /// { best, last, loss }: the best of the first three reps, the mean of the last two, and how
    /// much slower the last are (0.3: 30 % slower). Nil under 4 reps.
    static func summary(_ sizes: [Double]) -> [String: Double]? {
        guard sizes.count >= 4, let best = sizes.prefix(3).max(), best > 0 else { return nil }
        let last = (sizes[sizes.count - 1] + sizes[sizes.count - 2]) / 2
        let r = { (v: Double) in (v * 1000).rounded() / 1000 }
        return ["best": r(best), "last": r(last), "loss": r(max(0, 1 - last / best))]
    }

    /// The set is near failure (MyGym, calmer since 2026-11-14): the last TWO reps each `limit`
    /// (0.3: 30 %) slower than the best of the first three, and no sooner than 60 % of the goal (at
    /// least rep 4). The old rule (one slow rep, or one long gap) fired in 12 of 17 sets, often
    /// mid-set; this one fired in 5 of 16, 0-2 reps before the end in most.
    static func fatigued(sizes: [Double], times: [Double], limit: Double, goal: Double? = nil) -> Bool {
        let need = max(4, Int(((goal ?? 0) * 0.6).rounded(.up)))
        guard limit > 0, sizes.count >= need, let best = sizes.prefix(3).max() else { return false }
        let slow = (1 - limit) * best
        return sizes[sizes.count - 1] < slow && sizes[sizes.count - 2] < slow
    }
}

/// How long the wrist has been still: the acceleration's RMS over about half a second under `floor`.
/// Measured on the user's sets: still 0.02-0.04 g, lifting 0.1-0.6 g.
struct Stillness {
    static let floor = 0.06
    private(set) var stillSince: Double?
    private var ms = 0.0
    private var started = false

    /// One sample: t in seconds, userAcceleration in g.
    mutating func push(t: Double, ax: Double, ay: Double, az: Double, hz: Double = MotionLog.hz) {
        let m = ax * ax + ay * ay + az * az
        ms = started ? ms + (m - ms) * 2 / hz : m
        started = true
        if ms.squareRoot() < Stillness.floor {
            if stillSince == nil { stillSince = t }
        } else {
            stillSince = nil
        }
    }

    func stillFor(at t: Double) -> Double { stillSince.map { t - $0 } ?? 0 }
}

/// MyGym: one rep counted twice (the two counters, or a counter's "two at once") came within a
/// fraction of a second of the one before. A rep is let through only after at least `minGap`
/// seconds and `relGap` times the median gap so far. Replayed on 29 checked sets of 11-14 Nov:
/// mean error 2.21 -> 1.97 reps, overcount +0.97 -> +0.38.
struct RepGate {
    static let minGap = 0.8, relGap = 0.35
    private(set) var times: [Double] = []

    mutating func admit(_ t: Double) -> Bool {
        if let last = times.last {
            let gaps = zip(times.dropFirst(), times).map { $0 - $1 }.sorted()
            let median = gaps.isEmpty ? 0 : gaps[gaps.count / 2]
            if t - last < max(RepGate.minGap, RepGate.relGap * median) { return false }
        }
        times.append(t)
        return true
    }
}
