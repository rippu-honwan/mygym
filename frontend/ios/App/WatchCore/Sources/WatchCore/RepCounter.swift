import Foundation

/*
 * Counts reps while a set is recorded (docs/dev/rep-counter.md), one sample at a time, from the
 * gravity vector: which way the watch points. In most exercises the wrist turns one way going up
 * and back coming down, so the vector zigzags between two directions.
 *
 *   A reversal is a turning point; the stretch between two of them is a segment.
 *   A turning point that lands where the one before last did (the same end of the movement, and a
 *   segment about as long as the last) is half a rep proven: the wrist went there and came back.
 *   The first such return proves the two segments behind it too.
 *
 * What it cannot see: a movement that does not turn the wrist (a barbell bench press). It counts
 * a movement repeated while getting into position as a rep. And a turning point only shows once
 * the wrist has moved on from it (by `back`, a good third of the way): a rep is counted a moment
 * into the next one, the last rep when the wrist comes up to tap Done.
 */
struct RepCounter {
    // ponytail: tuned on the user's one workout of 2026-11-11 (of 12 sets with whole data, 10 within one
    // rep of what he logged). Knobs to tune again with more data, not truths.
    /// Seconds the gravity vector is smoothed over.
    static let smooth = 0.12
    /// Seconds over which "how much the wrist moves lately" is measured.
    static let tau = 1.5
    /// A reversal: this many times that movement back from the farthest point (at least minBack).
    static let back = 1.2
    static let minBack = 0.04
    /// A segment shorter than this (in g: 0.1 is about 6 degrees), or outside these seconds, is no rep's half.
    static let minAmp = 0.1
    static let minSeg = 0.25
    static let maxSeg = 6.0
    /// "Where the one before last was": within this many times the smaller of the two segments.
    static let near = 1.0

    private(set) var reps = 0
    private var half = 0
    private var run = 0
    private let a: Double, b: Double
    private var g: SIMD3<Double>?
    private var mean = SIMD3<Double>()
    private var spread = 0.0
    /// The last turning point, the farthest point from it so far, and when each was.
    private var from = SIMD3<Double>(), far = SIMD3<Double>()
    private var farDist = 0.0, fromAt = 0.0, farAt = 0.0
    /// The last two turning points, each with the length of the segment that ended there.
    private var points: [(SIMD3<Double>, Double)] = []

    init(hz: Double = MotionLog.hz) {
        a = 1 / hz / RepCounter.smooth
        b = 1 / hz / RepCounter.tau
    }

    private static func length(_ v: SIMD3<Double>) -> Double { (v * v).sum().squareRoot() }

    /// One sample (t in seconds, gravity in g). True when it completed a rep.
    mutating func push(t: Double, gx: Double, gy: Double, gz: Double) -> Bool {
        let x = SIMD3(gx, gy, gz)
        guard var s = g else {
            g = x; mean = x; from = x; far = x; fromAt = t; farAt = t
            // Where the set starts is a place to come back to: the first rep counts when it does.
            points = [(x, 0)]
            return false
        }
        s += (x - s) * a
        g = s
        mean += (s - mean) * b
        spread += (((s - mean) * (s - mean)).sum() - spread) * b
        let d = RepCounter.length(s - from)
        if d > farDist {
            farDist = d; far = s; farAt = t
            return false
        }
        guard RepCounter.length(s - far) >= max(RepCounter.minBack, RepCounter.back * spread.squareRoot()) else { return false }
        let counted = turn(at: far, length: farDist, took: farAt - fromAt)
        from = far; fromAt = farAt
        farDist = RepCounter.length(s - from); far = s; farAt = t
        return counted
    }

    private mutating func turn(at p: SIMD3<Double>, length: Double, took: Double) -> Bool {
        let before = reps
        let ok = length >= RepCounter.minAmp && took >= RepCounter.minSeg && took <= RepCounter.maxSeg
        var returned = false
        if ok, points.count >= 2 {
            let last = points[points.count - 1].1
            returned = last > 0 && RepCounter.length(p - points[points.count - 2].0) <= RepCounter.near * min(length, last)
                && length / last >= 0.5 && length / last <= 2
        }
        if returned {
            run += 1
            half += run == 1 ? 2 : 1
        } else {
            run = 0
        }
        points = ok ? Array((points + [(p, length)]).suffix(2)) : []
        reps = half / 2
        return reps > before
    }
}
