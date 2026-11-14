import XCTest
@testable import WatchCore

final class RepFusionTests: XCTestCase {
    func testSpeedFirstAndOneRepOnce() {
        var f = RepFusion()
        for t in [1.0, 3, 5, 7, 9] { f.event(t: t, from: "speed"); f.event(t: t + 0.2, from: "tilt") }
        XCTAssertEqual(f.count, 5, "the tilt counter's reps of the same moves do not add up")
        XCTAssertEqual(f.event(t: 9.3, from: "speed"), 0, "0.3 s after a rep: the same rep")
    }

    func testTiltWhenSpeedSeesLittle() {
        var f = RepFusion()
        f.event(t: 2, from: "speed")
        for t in [1.0, 3, 5, 7, 9, 11] { f.event(t: t, from: "tilt") }
        XCTAssertEqual(f.source, "tilt")
        XCTAssertEqual(f.count, 6)
    }

    func testTheEnds() {
        var f = RepFusion()
        for t in [0.0, 8, 10, 12, 14, 16] { f.event(t: t, from: "speed") }
        XCTAssertEqual(f.times.first, 8, "a first move far before the run is taken back")
        f.event(t: 30, from: "speed")
        XCTAssertEqual(f.count, 5, "a move long after the run waits")
        var g = RepFusion()
        for t in [0.0, 2, 4, 6, 8, 13, 15] { g.event(t: t, from: "speed") }
        XCTAssertEqual(g.count, 7, "a slow rep the next one confirms counts")
    }

    /// Two of the user's sets (2026-11-13), both counters run on them: the counts are the tuning
    /// script's (counter3.py), so the two stay the same counter. Truth: 9 and 10.
    func testRealSets() throws {
        for (name, expected) in [("fusion-speed", 9), ("fusion-tilt", 12)] {
            let url = try XCTUnwrap(Bundle.module.url(forResource: name, withExtension: "csv", subdirectory: "Fixtures"))
            var speed = RepCounter(), tilt = TiltCounter(), f = RepFusion()
            for line in try String(contentsOf: url, encoding: .utf8).split(separator: "\n").dropFirst() {
                let v = line.split(separator: ",").compactMap { Double($0) }
                let (s0, t0) = (speed.reps, tilt.reps)
                speed.push(t: v[0], ax: v[1], ay: v[2], az: v[3])
                _ = tilt.push(t: v[0], gx: v[4], gy: v[5], gz: v[6])
                for _ in s0..<speed.reps { f.event(t: v[0], from: "speed") }
                for _ in t0..<tilt.reps { f.event(t: v[0], from: "tilt") }
            }
            XCTAssertEqual(f.count, expected, name)
        }
    }
}
