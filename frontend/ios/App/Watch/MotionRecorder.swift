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
    /// A rep was counted; called on the main queue.
    var onRep: (() -> Void)?

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
            let before = self.counter.reps
            // Two at once when the counter finds that the reps changed (RepCounter.swing).
            for _ in before..<self.counter.push(t: s.t, ax: s.ax, ay: s.ay, az: s.az) {
                DispatchQueue.main.async { self.onRep?() }
            }
            if self.samples.count > cap { MotionLog.trim(&self.samples, now: s.t) }
        }
    }

    func stop() {
        manager.stopDeviceMotionUpdates()
        queue.addOperation { [weak self] in self?.samples = [] }
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
