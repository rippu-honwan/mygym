import Foundation

/*
 * Motion data per set, for the rep counter (docs/dev/rep-counter.md). While a workout runs the
 * watch keeps the last few minutes of deviceMotion samples (Watch/MotionRecorder.swift); when a
 * set is ticked, the samples from the set's start to the tick become one CSV file for the phone.
 */
struct MotionSample: Equatable {
    /// Seconds since 1970.
    var t: Double
    /// userAcceleration in g (gravity removed).
    var ax: Double, ay: Double, az: Double
    /// rotationRate in rad/s.
    var rx: Double, ry: Double, rz: Double
    /// gravity in g: which way the watch points.
    var gx: Double, gy: Double, gz: Double
}

enum MotionLog {
    // ponytail: fixed rate, a calibration knob; 50 Hz is 100-150 samples per curl rep.
    static let hz: Double = 50
    /// How far back the watch keeps samples: longer than any set plus its setup.
    static let keepSec: Double = 300

    /// The watch is on the wrist: leg exercises barely move it, so they are not recorded.
    /// No body part (a custom exercise): recorded.
    static func records(bodyPart: String?) -> Bool {
        bodyPart != "upper legs" && bodyPart != "lower legs"
    }

    static func window(_ s: [MotionSample], from: Double, to: Double) -> [MotionSample] {
        s.filter { $0.t >= from && $0.t <= to }
    }

    /// Drops the samples older than `keepSec` before `now`.
    static func trim(_ s: inout [MotionSample], now: Double) {
        if let i = s.firstIndex(where: { $0.t >= now - keepSec }), i > 0 { s.removeFirst(i) }
    }

    /// Line 1: `# ` and the set's metadata as JSON. Then a header and one row per sample, with
    /// `t` in seconds since `from` (the set's start).
    /// A whole workout's heart rate: line 1 `# ` and its metadata, then `t,bpm` with t in seconds
    /// from the first reading. The phone and the server take it like a set's file.
    static func heartRateCSV(_ readings: [(t: Double, bpm: Double)], wid: String?, extra: [String: Any] = [:]) -> String? {
        guard let first = readings.first?.t, let last = readings.last?.t else { return nil }
        var m = extra
        for (k, v) in ["v": 1, "kind": "hr", "exId": "hr", "start": (first * 1000).rounded(), "end": (last * 1000).rounded()] as [String: Any] { m[k] = v }
        if let wid = wid { m["wid"] = wid }
        let json = (try? JSONSerialization.data(withJSONObject: m, options: [.sortedKeys]))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
        var out = "# \(json)\nt,bpm\n"
        for r in readings { out += String(format: "%.1f,%.0f\n", r.t - first, r.bpm) }
        return out
    }

    static func csv(_ s: [MotionSample], from: Double, meta: [String: Any]) -> String {
        var m = meta
        m["v"] = 1
        m["hz"] = hz
        let json = (try? JSONSerialization.data(withJSONObject: m, options: [.sortedKeys]))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
        var out = "# \(json)\nt,ax,ay,az,rx,ry,rz,gx,gy,gz\n"
        out.reserveCapacity(out.count + s.count * 80)
        for x in s {
            out += String(format: "%.3f", x.t - from)
            for v in [x.ax, x.ay, x.az, x.rx, x.ry, x.rz, x.gx, x.gy, x.gz] {
                out += String(format: ",%.4f", v)
            }
            out += "\n"
        }
        return out
    }

    /// `20261109-193005_0031_s2.csv`: local start time, exercise id, set number (from 1).
    static func fileName(start: Double, exId: String, set: Int, zone: TimeZone = .current) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = zone
        f.dateFormat = "yyyyMMdd-HHmmss"
        let safeId = exId.filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }
        return "\(f.string(from: Date(timeIntervalSince1970: start)))_\(safeId)_s\(set).csv"
    }
}
