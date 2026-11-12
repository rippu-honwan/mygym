import XCTest
@testable import WatchCore

final class SetSpeedTests: XCTestCase {
    func testSummary() {
        XCTAssertNil(SetSpeed.summary([1, 1, 1]))
        let s = SetSpeed.summary([0.9, 1.0, 0.95, 0.8, 0.7, 0.5])
        XCTAssertEqual(s?["best"], 1.0)
        XCTAssertEqual(s?["last"], 0.6)
        XCTAssertEqual(s?["loss"], 0.4)
    }

    func testFatigued() {
        let t = [0.0, 2, 4, 6, 8, 10]
        XCTAssertFalse(SetSpeed.fatigued(sizes: [1, 1, 1, 0.9, 0.85, 0.8], times: t, limit: 0.3))
        XCTAssertTrue(SetSpeed.fatigued(sizes: [1, 1, 1, 0.9, 0.8, 0.6], times: t, limit: 0.3))
        XCTAssertFalse(SetSpeed.fatigued(sizes: [1, 1, 1, 0.9, 0.8, 0.6], times: t, limit: 0), "off")
        XCTAssertFalse(SetSpeed.fatigued(sizes: [1, 1, 0.5], times: [0, 2, 4], limit: 0.3), "too soon")
        XCTAssertTrue(SetSpeed.fatigued(sizes: [1, 1, 1, 1, 1, 1], times: [0, 2, 4, 6, 8, 13], limit: 0.3), "a grind")
    }

    func testStillness() {
        var s = Stillness()
        var t = 0.0
        for i in 0..<100 { s.push(t: t, ax: 0.4 * sin(Double(i) / 3), ay: 0, az: 0); t += 0.02 }
        XCTAssertEqual(s.stillFor(at: t), 0, "lifting")
        for _ in 0..<350 { s.push(t: t, ax: 0.01, ay: 0.01, az: 0); t += 0.02 }
        XCTAssertGreaterThan(s.stillFor(at: t), 4, "still for the last seconds")
    }
}
