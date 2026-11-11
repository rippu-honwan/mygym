import XCTest
@testable import WatchCore

final class RepCounterTests: XCTestCase {
    /// The wrist going up and down `count` times along x (a sine, `reach` metres each way,
    /// `period` seconds per rep), after and before `idle` seconds still.
    private func lift(count: Int, period: Double, reach: Double, idle: Double = 3) -> Int {
        var c = RepCounter()
        let hz = MotionLog.hz, w = 2 * Double.pi / period
        var t = 0.0
        func feed(_ a: Double) { c.push(t: t, ax: a / 9.81, ay: 0, az: 0); t += 1 / hz }
        for _ in 0..<Int(idle * hz) { feed(0) }
        // position reach * (1 - cos wt): acceleration reach * w^2 * cos wt
        // A quarter of a rep more at the end: the weight going back to its rack. A rep is counted
        // when the wrist moves on after it.
        // ponytail: a set that ends dead still loses its last rep (the user's curl: 9 of 10); "still
        // for half a second" as a rep's end counted too much on his gym sets.
        let n = count == 0 ? 0 : Int((Double(count) + 0.25) * period * hz)
        for i in 0..<n { feed(reach * w * w * cos(w * Double(i) / hz)) }
        for _ in 0..<Int(idle * hz) { feed(0) }
        return c.reps
    }

    func testCountsEveryUpAndDown() {
        XCTAssertEqual(lift(count: 10, period: 2.5, reach: 0.25), 10, "a press")
        XCTAssertEqual(lift(count: 8, period: 3.5, reach: 0.3), 8, "slow reps")
        XCTAssertEqual(lift(count: 12, period: 1.2, reach: 0.15), 12, "fast reps")
    }

    func testAStillWristIsNoRep() {
        XCTAssertEqual(lift(count: 0, period: 2, reach: 0.3), 0)
        XCTAssertEqual(lift(count: 6, period: 2, reach: 0.005), 0, "a tremble is no rep")
    }

    /// the user's own sets of 2026-11-11 (acceleration only). The counts are what the tuning script
    /// (docs/dev/rep-counter-tools/counter2.py) counts: the two must stay the same counter.
    func testKensRealSets() throws {
        // bench and curl: 10 real reps each (he counted). row: 16 logged.
        for (name, expected) in [("reps-bench-10", 10), ("reps-curl-10", 9), ("reps-row-16", 20)] {
            let url = try XCTUnwrap(Bundle.module.url(forResource: name, withExtension: "csv", subdirectory: "Fixtures"))
            var c = RepCounter()
            for line in try String(contentsOf: url, encoding: .utf8).split(separator: "\n").dropFirst() {
                let v = line.split(separator: ",").compactMap { Double($0) }
                c.push(t: v[0], ax: v[1], ay: v[2], az: v[3])
            }
            XCTAssertEqual(c.reps, expected, name)
        }
    }
}
