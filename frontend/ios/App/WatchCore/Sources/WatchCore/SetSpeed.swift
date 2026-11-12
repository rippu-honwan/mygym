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

    /// The set is near failure: the last rep `limit` (0.3: 30 %) slower than the best of the first
    /// three, or it took more than twice as long as the reps before it (a grind). From rep 4 on.
    static func fatigued(sizes: [Double], times: [Double], limit: Double) -> Bool {
        guard limit > 0, sizes.count >= 4, let best = sizes.prefix(3).max(), let last = sizes.last else { return false }
        if last < (1 - limit) * best { return true }
        let gaps = zip(times.dropFirst(), times).map { $0 - $1 }
        guard gaps.count >= 4, let g = gaps.last else { return false }
        let earlier = gaps.dropLast().sorted()
        return g > 2 * earlier[earlier.count / 2]
    }
}

/// How long the wrist has been still: the acceleration's RMS over about half a second under `floor`.
/// Measured on Ken's sets: still 0.02-0.04 g, lifting 0.1-0.6 g.
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
