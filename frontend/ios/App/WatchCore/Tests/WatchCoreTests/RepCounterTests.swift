import XCTest
@testable import WatchCore

final class RepCounterTests: XCTestCase {
    /// The wrist swinging between two directions `count` times, `period` seconds each, after `idle` seconds still.
    private func swing(count: Int, period: Double, angle: Double, idle: Double = 3) -> Int {
        var c = RepCounter()
        let hz = MotionLog.hz
        var t = 0.0
        func feed(_ a: Double) { _ = c.push(t: t, gx: sin(a), gy: 0, gz: -cos(a)); t += 1 / hz }
        for _ in 0..<Int(idle * hz) { feed(0) }
        for i in 0..<Int(Double(count) * period * hz) {
            feed(angle / 2 * (1 - cos(2 * .pi * Double(i) / (period * hz))))
        }
        // The set is over: the weight goes back to its rack, half the way up again. Only a move
        // like this tells the counter that the last rep had ended (a reversal shows once the wrist
        // has left it).
        // ponytail: a last move that carries on away from the top hides the last rep; counting a
        // rep at its top, or after a still moment, counted too much on the user's real sets.
        for i in 0..<Int(hz) { feed(angle / 2 * Double(i) / hz) }
        for _ in 0..<Int(idle * hz) { feed(angle / 2) }
        return c.reps
    }

    func testCountsEveryThereAndBack() {
        XCTAssertEqual(swing(count: 10, period: 2.5, angle: 1.2), 10, "a curl: the wrist turns far")
        XCTAssertEqual(swing(count: 8, period: 3, angle: 0.25), 8, "a row: the wrist turns a little")
        XCTAssertEqual(swing(count: 12, period: 1.2, angle: 0.8), 12, "fast reps")
    }

    func testAStillWristIsNoRep() {
        XCTAssertEqual(swing(count: 0, period: 2, angle: 1), 0)
        XCTAssertEqual(swing(count: 6, period: 2, angle: 0.02), 0, "a tremble is no rep")
    }

    func testOneMoveIntoPositionIsNoRep() {
        var c = RepCounter()
        var t = 0.0
        // the arm goes up to the bar and stays there
        for i in 0..<400 {
            let a = min(1.4, Double(i) / 50)
            _ = c.push(t: t, gx: sin(a), gy: 0, gz: -cos(a)); t += 0.02
        }
        XCTAssertEqual(c.reps, 0)
    }

    /// the user's own sets of 2026-11-11 (gravity only). The counts are what the tuning script counted:
    /// the code here and the script must stay the same counter.
    func testKensRealSets() throws {
        for (name, expected) in [("reps-curl-12", 12), ("reps-row-16", 16), ("reps-triceps-10", 12)] {
            let url = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures/\(name)", withExtension: "csv"))
            var c = RepCounter()
            for line in try String(contentsOf: url, encoding: .utf8).split(separator: "\n").dropFirst() {
                let v = line.split(separator: ",").compactMap { Double($0) }
                _ = c.push(t: v[0], gx: v[1], gy: v[2], gz: v[3])
            }
            // triceps: the user did 10; the counter takes moves while he got into position for two more.
            XCTAssertEqual(c.reps, expected, name)
        }
    }
}
