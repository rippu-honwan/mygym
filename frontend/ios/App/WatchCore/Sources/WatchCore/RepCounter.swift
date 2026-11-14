import Foundation

/*
 * Counts reps while a set is recorded (docs/dev/rep-counter.md), one sample at a time, from the
 * watch's acceleration. Version 2: the velocity along the movement; a rep is one full swing of it.
 *
 *   1. userAcceleration (device frame, in g) minus its slow mean, integrated with a leak and
 *      smoothed: a velocity vector that forgets drift.
 *   2. Its main axis lately (a running covariance, one power-iteration step per sample); x is
 *      the velocity along it.
 *   3. A swing: x above +th after having been below -th (th follows the recent size of x). The
 *      crossing is where the movement turns round: the lowest or the highest point.
 *   4. A swing counts when it is like the swings before it in size and period. One that is not
 *      is ignored; when the swing after a lone first one does not match it, that first one was
 *      getting into position, and the swing takes its place (the count stays).
 *
 * Version 1 watched the wrist's tilt (the gravity vector): it missed the first reps and most of
 * a bench press, where the wrist hardly tilts.
 * The tuning twin is docs/dev/rep-counter-tools/counter2.py: keep the two the same counter.
 */
struct RepCounter {
    // ponytail: tuned on the user's sets of 2026-11-11 (home, 10 real reps each: 10, 10, 10, 9; gym,
    // 12 whole sets: 10 within one rep of what he logged). Knobs to tune again with more data.
    /// Seconds: the slow mean taken off the acceleration, the leak of the integrator, the smoothing.
    static let highPass = 1.0, leak = 0.8, smooth = 0.12
    /// Seconds over which the main axis and the size of the velocity are measured.
    static let tau = 3.0
    /// A swing crosses this many times the recent RMS of the velocity (at least `floor`, m/s).
    static let k = 1.0, floor = 0.05
    /// A swing smaller than this (m/s, top to bottom) or sooner than this (s) after the last is none.
    static let minSize = 0.15, minPeriod = 0.6
    /// "Like the swings before": size and period within these times their median (of the last 5).
    static let sizeRange = 0.5...2.2, periodRange = 0.5...2.0

    private(set) var reps = 0
    /// Each counted rep's swing size (its speed, top to bottom) and when it was counted: the set's
    /// speed summary and the fatigue alert (SetSpeed).
    private(set) var repSizes: [Double] = [], repTimes: [Double] = []
    /// When each counted rep began: the swing before it ended there (the first: the movement's
    /// first turn). With repTimes, each rep's start and end (MyGym raw data).
    private(set) var repStarts: [Double] = []
    /// When the movement first turned, for the first rep's start.
    private var firstTurn: Double?
    private let dt: Double
    private var mean: SIMD3<Double>?
    private var v = SIMD3<Double>(), vs = SIMD3<Double>()
    /// The running covariance of vs, row by row, and its main axis.
    private var cov = [SIMD3<Double>(), SIMD3<Double>(), SIMD3<Double>()]
    private var axis = SIMD3<Double>(1, 0, 0)
    private var ms = 0.0
    private var state = 0, top = 0.0, bottom = 0.0
    private var last: Double?
    /// The swings counted in the current run of reps.
    private var sizes: [Double] = [], periods: [Double] = []
    /// The size of a swing that did not fit.
    private var odd: Double?

    init(hz: Double = MotionLog.hz) { dt = 1 / hz }

    /// One sample: t in seconds, userAcceleration in g. Returns the reps so far.
    @discardableResult
    mutating func push(t: Double, ax: Double, ay: Double, az: Double) -> Int {
        let a = SIMD3(ax, ay, az) * 9.81
        var m = mean ?? a
        m += (a - m) * (dt / RepCounter.highPass)
        mean = m
        v += (a - m) * dt
        v -= v * (dt / RepCounter.leak)
        vs += (v - vs) * (dt / RepCounter.smooth)
        let b = dt / RepCounter.tau
        for i in 0..<3 { cov[i] += (vs * vs[i] - cov[i]) * b }
        let n = SIMD3((cov[0] * axis).sum(), (cov[1] * axis).sum(), (cov[2] * axis).sum())
        let length = (n * n).sum().squareRoot()
        if length > 0 { axis = n / length }
        let x = (vs * axis).sum()
        ms += (x * x - ms) * b
        let th = max(RepCounter.floor, RepCounter.k * ms.squareRoot())
        top = max(top, x); bottom = min(bottom, x)
        if x < -th, state >= 0 {
            state = -1
            if firstTurn == nil { firstTurn = t }
        } else if x > th, state <= 0 {
            let was = state
            state = 1
            if was < 0 {
                let period = last.map { t - $0 }
                if period == nil || period! >= RepCounter.minPeriod {
                    swing(size: top - bottom, period: period, t: t, start: last ?? firstTurn ?? t)
                    last = t
                    top = x; bottom = 0
                }
            } else {
                top = x; bottom = 0
            }
        }
        return reps
    }

    private static func median(_ a: ArraySlice<Double>) -> Double {
        let s = a.sorted()
        return s.count % 2 == 1 ? s[s.count / 2] : (s[s.count / 2 - 1] + s[s.count / 2]) / 2
    }

    private func like(_ size: Double, _ period: Double?, sizes: [Double], periods: [Double]) -> Bool {
        let m = RepCounter.median(sizes.suffix(5))
        guard size >= RepCounter.sizeRange.lowerBound * m, size <= RepCounter.sizeRange.upperBound * m else { return false }
        guard let period = period, !periods.isEmpty else { return true }
        let p = RepCounter.median(periods.suffix(5))
        return period >= RepCounter.periodRange.lowerBound * p && period <= RepCounter.periodRange.upperBound * p
    }

    private mutating func swing(size: Double, period: Double?, t: Double, start: Double) {
        guard size >= RepCounter.minSize else { return }
        if sizes.isEmpty {
            sizes = [size]; periods = []; reps += 1
            repSizes.append(size); repTimes.append(t); repStarts.append(start)
        } else if like(size, period, sizes: sizes, periods: periods) {
            sizes.append(size); odd = nil
            if let p = period { periods.append(p) }
            reps += 1
            repSizes.append(size); repTimes.append(t); repStarts.append(start)
        } else if sizes.count == 1 {
            // The lone first swing was getting into position: this one is rep 1 in its place.
            sizes = [size]; periods = []; odd = nil
            if !repSizes.isEmpty {
                repSizes[repSizes.count - 1] = size; repTimes[repTimes.count - 1] = t; repStarts[repStarts.count - 1] = start
            }
        } else if let o = odd, like(size, nil, sizes: [o], periods: []) {
            // Two alike in a row, unlike the reps before: the reps changed, both count.
            sizes = [o, size]; periods = period.map { [$0] } ?? []; odd = nil
            reps += 2
            repSizes += [o, size]; repTimes += [start, t]; repStarts += [oddStart ?? start, start]
        } else {
            odd = size
            oddStart = start
        }
    }
    /// When the swing that did not fit began.
    private var oddStart: Double?
}
