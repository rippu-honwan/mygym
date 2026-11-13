// MyGym debugging (docs/dev/rep-counter.md): what the iPhone sent to the Apple Watch and heard
// back, line by line, kept on the phone (the last 800 lines) and uploaded to the Mac as one file
// a day (PUT /api/motion, `<day>-000000_synclog_s0.csv`) a few seconds after the last line.
import { api } from './api.js'
import { MOBILE } from './mobile.js'

const KEY = 'gym_sync_log_v1'
let timer = null
const pad = (n, w = 2) => String(n).padStart(w, '0')

export function syncLog (line) {
  if (!MOBILE) return
  try {
    const d = new Date()
    const all = JSON.parse(localStorage.getItem(KEY) || '[]')
    all.push(`${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)} ${line}`)
    localStorage.setItem(KEY, JSON.stringify(all.slice(-800)))
  } catch { /* storage full or off: nothing to keep */ }
  clearTimeout(timer)
  timer = setTimeout(uploadSyncLog, 10000)
}

export async function uploadSyncLog () {
  try {
    const lines = JSON.parse(localStorage.getItem(KEY) || '[]')
    if (!lines.length) return
    const d = new Date()
    const name = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-000000_synclog_s0.csv`
    await api('/api/motion', { method: 'PUT', body: JSON.stringify({ name, csv: '# {"kind":"synclog","v":1}\n' + lines.join('\n') + '\n' }) })
  } catch { /* offline or not paired: the next line tries again */ }
}

/** A snapshot in a few words: the exercise up, each exercise's sets done, the rest, a phone Start. */
export function snapLine (snap) {
  const a = snap && snap.active
  if (!a) return 'snap -> no workout'
  const done = (a.entries || []).map((e, i) => `${i}:${(e.sets || []).filter(s => s.done).length}/${(e.sets || []).length}`).join(' ')
  return `snap -> w=${a.id} cur=${a.cur} [${done}] rest=${a.rest ? 'on' : 'off'}${a.startSet ? ` start=e${a.startSet.entryIdx}s${a.startSet.setIdx}` : ''}`
}
