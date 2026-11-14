import CoreMotion
import Foundation
import WatchConnectivity

/*
 * Motion data for the rep counter (docs/dev/rep-counter.md, WatchCore MotionLog.swift).
 *
 * deviceMotion at MotionLog.hz from Start set to Done (SessionStore.startSet / completeSet), at
 * most the last MotionLog.keepSec kept. It runs on the workout session's background time: with
 * Apple Health off there is no session, and the watch stops it once the wrist drops.
 *
 * Each set becomes one CSV in `outbox`, sent to the phone with transferFile. A file is deleted
 * only once its transfer finished without an error (SessionStore didFinish fileTransfer);
 * whatever is left is sent again at the next start.
 */
final class MotionRecorder {
    private let manager = CMMotionManager()
    private let queue: OperationQueue = {
        let q = OperationQueue()
        q.maxConcurrentOperationCount = 1
        q.name = "motion"
        return q
    }()
    /// Only touched on `queue`.
    private var samples: [MotionSample] = []
    /// Counts the reps of the set being recorded, sample by sample (WatchCore RepCounter); only
    /// touched on `queue`.
    private var counter = RepCounter()
    /// The second counter, on the wrist's tilt: it sees slow reps the speed counter misses.
    private var tilt = TiltCounter()
    /// How long the wrist has been still (auto-end of a set); only touched on `queue`.
    private var stillness = Stillness()
    /// MyGym: lets a rep through only once (RepGate), and every rep let through as [start, end,
    /// speed (the speed counter's swing size, nil for a rep only the tilt saw), source], seconds
    /// since 1970; only touched on `queue`.
    private var gate = RepGate()
    private var repLog: [(Double, Double, Double?, String)] = []
    private var lastT = 0.0
    /// A rep was counted; called on the main queue with when (seconds since 1970) and which counter
    /// saw it first: "speed", "tilt" or "both" (the set file's log, for debugging the counter).
    var onRep: ((Double, String) -> Void)?

    static var outbox: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("motion-outbox", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// A fresh recording: what an earlier one left is dropped.
    func start() {
        guard manager.isDeviceMotionAvailable else { return }
        if manager.isDeviceMotionActive { manager.stopDeviceMotionUpdates() }
        queue.addOperation { [weak self] in
            self?.samples = []
            self?.counter = RepCounter()
            self?.tilt = TiltCounter()
            self?.stillness = Stillness()
            self?.gate = RepGate()
            self?.repLog = []
        }
        MotionRecorder.resendLeftovers()
        manager.deviceMotionUpdateInterval = 1 / MotionLog.hz
        // deviceMotion's timestamp counts from boot; this makes it seconds since 1970.
        let bootAt = Date().timeIntervalSince1970 - ProcessInfo.processInfo.systemUptime
        let cap = Int(MotionLog.hz * MotionLog.keepSec * 1.2)
        manager.startDeviceMotionUpdates(to: queue) { [weak self] m, _ in
            guard let self = self, let m = m else { return }
            let a = m.userAcceleration, r = m.rotationRate, g = m.gravity
            let s = MotionSample(t: bootAt + m.timestamp, ax: a.x, ay: a.y, az: a.z,
                                 rx: r.x, ry: r.y, rz: r.z, gx: g.x, gy: g.y, gz: g.z)
            self.samples.append(s)
            self.stillness.push(t: s.t, ax: s.ax, ay: s.ay, az: s.az)
            self.lastT = s.t
            // The larger of the two counts (docs/dev/rep-counter.md): speed misses slow reps,
            // tilt misses reps that hardly turn the wrist. Two at once when one counter jumps.
            // ponytail: max adds up both counters' overcounts; a fused signal is the next step.
            let before = max(self.counter.reps, self.tilt.reps)
            let (v0, t0) = (self.counter.reps, self.tilt.reps)
            self.counter.push(t: s.t, ax: s.ax, ay: s.ay, az: s.az)
            _ = self.tilt.push(t: s.t, gx: s.gx, gy: s.gy, gz: s.gz)
            let source = self.counter.reps > v0 && self.tilt.reps > t0 ? "both" : self.counter.reps > v0 ? "speed" : "tilt"
            for _ in before..<max(self.counter.reps, self.tilt.reps) {
                let t = s.t
                guard self.gate.admit(t) else { continue }
                // the speed counter's own rep when it counted this one: its start and speed
                let speed = self.counter.reps > v0 && !self.counter.repSizes.isEmpty
                let start = speed ? (self.counter.repStarts.last ?? t) : (self.repLog.last?.1 ?? t)
                self.repLog.append((start, t, speed ? self.counter.repSizes.last : nil, source))
                DispatchQueue.main.async { self.onRep?(t, source) }
            }
            if self.samples.count > cap { MotionLog.trim(&self.samples, now: s.t) }
        }
    }

    func stop() {
        manager.stopDeviceMotionUpdates()
        queue.addOperation { [weak self] in self?.samples = [] }
    }

    /// The set so far: each counted rep's speed and time (the speed counter's), and how many
    /// seconds the wrist has been still.
    /// Every rep let through in this set, [start, end, speed or nil, source] (seconds since 1970).
    func reps() -> [(Double, Double, Double?, String)] {
        var out: [(Double, Double, Double?, String)] = []
        let op = BlockOperation { [weak self] in out = self?.repLog ?? [] }
        queue.addOperations([op], waitUntilFinished: true)
        return out
    }

    func status() -> (sizes: [Double], times: [Double], still: Double) {
        var out: (sizes: [Double], times: [Double], still: Double) = ([], [], 0)
        let op = BlockOperation { [weak self] in
            guard let self = self else { return }
            out = (self.counter.repSizes, self.counter.repTimes, self.stillness.stillFor(at: self.lastT))
        }
        queue.addOperations([op], waitUntilFinished: true)
        return out
    }

    /// The samples between two moments, seconds since 1970.
    func window(from: Double, to: Double) -> [MotionSample] {
        var out: [MotionSample] = []
        let op = BlockOperation { [weak self] in out = MotionLog.window(self?.samples ?? [], from: from, to: to) }
        queue.addOperations([op], waitUntilFinished: true)
        return out
    }

    /// One ticked set: its CSV written to the outbox and sent to the phone.
    func send(entry e: Entry, set si: Int, from: Date, to: Date, meta extra: [String: Any]) {
        guard MotionLog.records(bodyPart: e.bodyPart) else { return }
        let b = to.timeIntervalSince1970
        let a = max(from.timeIntervalSince1970, b - MotionLog.keepSec)
        let s = window(from: a, to: b)
        guard !s.isEmpty else { return }
        var meta = extra
        meta["exId"] = e.id
        meta["name"] = e.name
        meta["set"] = si + 1
        // the side of a per-side set, so its two sides stay two files (MyGym)
        if e.sets.indices.contains(si), meta["side"] == nil, let side = e.sets[si].sideUp { meta["side"] = side }
        meta["start"] = (a * 1000).rounded()
        meta["end"] = (b * 1000).rounded()
        if let bp = e.bodyPart { meta["bodyPart"] = bp }
        let url = MotionRecorder.outbox.appendingPathComponent(MotionLog.fileName(start: a, exId: e.id, set: si + 1))
        DispatchQueue.global(qos: .utility).async {
            do {
                try MotionLog.csv(s, from: a, meta: meta).write(to: url, atomically: true, encoding: .utf8)
            } catch { return }
            MotionRecorder.transfer(url)
        }
    }

    /// The finished workout's heart rate, every reading, as one file for the phone (the post-workout
    /// report shows when the heart rate was high).
    static func sendHeartRate(_ readings: [(Date, Double)], wid: String?, daily: [String: [[Any]]] = [:]) {
        let r = readings.map { (t: $0.0.timeIntervalSince1970, bpm: $0.1) }
        guard let first = r.first?.t, let csv = MotionLog.heartRateCSV(r, wid: wid, extra: daily.isEmpty ? [:] : ["daily": daily]) else { return }
        let url = outbox.appendingPathComponent(MotionLog.fileName(start: first, exId: "hr", set: 0))
        DispatchQueue.global(qos: .utility).async {
            do { try csv.write(to: url, atomically: true, encoding: .utf8) } catch { return }
            transfer(url)
        }
    }

    static func transfer(_ url: URL) {
        let session = WCSession.default
        guard WCSession.isSupported(), session.activationState == .activated else { return }
        session.transferFile(url, metadata: ["motion": url.lastPathComponent])
    }

    /// Files written but never confirmed sent (the app quit, a transfer failed): sent again.
    static func resendLeftovers() {
        let session = WCSession.default
        guard WCSession.isSupported(), session.activationState == .activated else { return }
        let pending = Set(session.outstandingFileTransfers.map { $0.file.fileURL.lastPathComponent })
        let files = (try? FileManager.default.contentsOfDirectory(at: outbox, includingPropertiesForKeys: nil)) ?? []
        for f in files where f.pathExtension == "csv" && !pending.contains(f.lastPathComponent) {
            transfer(f)
        }
    }

    /// A transfer finished: delete the file when it arrived; a failed one stays for the next start.
    static func finished(_ t: WCSessionFileTransfer, error: Error?) {
        guard t.file.metadata?["motion"] != nil else { return }
        let url = outbox.appendingPathComponent(t.file.fileURL.lastPathComponent)
        if error == nil { try? FileManager.default.removeItem(at: url) }
    }
}
