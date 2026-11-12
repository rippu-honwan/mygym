import XCTest
@testable import WatchCore

final class MotionLogTests: XCTestCase {
    func sample(_ t: Double, _ v: Double = 0) -> MotionSample {
        MotionSample(t: t, ax: v, ay: 0, az: 0, rx: 0, ry: 0, rz: 0, gx: 0, gy: 0, gz: -1)
    }

    func testLegExercisesAreSkippedEverythingElseIsRecorded() {
        XCTAssertTrue(MotionLog.records(bodyPart: "upper arms"))
        XCTAssertTrue(MotionLog.records(bodyPart: "chest"))
        XCTAssertTrue(MotionLog.records(bodyPart: nil), "a custom exercise has no body part")
        XCTAssertFalse(MotionLog.records(bodyPart: "upper legs"))
        XCTAssertFalse(MotionLog.records(bodyPart: "lower legs"))
    }

    func testTheWindowKeepsOnlyTheSet() {
        let s = (0..<10).map { sample(Double($0)) }
        XCTAssertEqual(MotionLog.window(s, from: 3, to: 5).map(\.t), [3, 4, 5])
        XCTAssertEqual(MotionLog.window(s, from: 20, to: 30), [])
    }

    func testTrimDropsWhatIsOlderThanTheKeptTime() {
        var s = (0..<1000).map { sample(Double($0)) }
        MotionLog.trim(&s, now: 999)
        XCTAssertEqual(s.first?.t, 999 - MotionLog.keepSec)
        XCTAssertEqual(s.last?.t, 999)
    }

    func testCsvHasMetadataHeaderAndRelativeTimes() throws {
        let s = [sample(100.0, 0.5), sample(100.02, -0.25)]
        let text = MotionLog.csv(s, from: 100, meta: ["exId": "0031", "reps": 10])
        let lines = text.split(separator: "\n").map(String.init)
        XCTAssertEqual(lines.count, 4)
        XCTAssertTrue(lines[0].hasPrefix("# "))
        let meta = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(lines[0].dropFirst(2).utf8)) as? [String: Any])
        XCTAssertEqual(meta["exId"] as? String, "0031")
        XCTAssertEqual(meta["reps"] as? Int, 10)
        XCTAssertEqual(meta["hz"] as? Double, MotionLog.hz)
        XCTAssertEqual(lines[1], "t,ax,ay,az,rx,ry,rz,gx,gy,gz")
        XCTAssertEqual(lines[2], "0.000,0.5000,0.0000,0.0000,0.0000,0.0000,0.0000,0.0000,0.0000,-1.0000")
        XCTAssertTrue(lines[3].hasPrefix("0.020,-0.2500,"))
    }

    func testFileNameSaysWhenWhatAndWhichSet() {
        let utc = TimeZone(identifier: "UTC")!
        // 2026-11-09 14:30:05 UTC
        XCTAssertEqual(MotionLog.fileName(start: 1_794_234_605, exId: "0031", set: 2, zone: utc),
                       "20261109-143005_0031_s2.csv")
    }

    func testAWorkoutsHeartRateFile() throws {
        XCTAssertNil(MotionLog.heartRateCSV([], wid: "w1"))
        let csv = try XCTUnwrap(MotionLog.heartRateCSV([(t: 1000, bpm: 98.4), (t: 1005.25, bpm: 121.6)], wid: "w1"))
        let lines = csv.split(separator: "\n").map(String.init)
        XCTAssertTrue(lines[0].hasPrefix("# {"))
        XCTAssertTrue(lines[0].contains("\"kind\":\"hr\"") && lines[0].contains("\"wid\":\"w1\"") && lines[0].contains("\"start\":1000000"))
        XCTAssertEqual(Array(lines.dropFirst()), ["t,bpm", "0.0,98", "5.2,122"])
        XCTAssertTrue(MotionLog.fileName(start: 1000, exId: "hr", set: 0).hasSuffix("_hr_s0.csv"))
    }
}
