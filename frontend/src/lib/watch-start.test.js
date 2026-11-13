import { describe, expect, it } from 'vitest'
import { buildSnapshot, recordingFromWatch } from './watch-sync.js'

// MyGym: Start set on the phone travels to the watch; the watch's recording comes back.
describe('Start set from the phone', () => {
  const S = { unit: 'kg', restSec: 90, active: { id: 'w1', name: 'A', cur: 0, entries: [{ id: '0577', sets: [{ w: 30, r: 8, done: false }] }] } }
  it('goes in the snapshot while fresh', () => {
    const at = Date.now()
    expect(buildSnapshot(S, { startSet: { entryIdx: 0, setIdx: 0, at } }).active.startSet).toEqual({ entryIdx: 0, setIdx: 0, at })
    expect(buildSnapshot(S, { startSet: { entryIdx: 0, setIdx: 0, at: at - 120e3 } }).active.startSet).toBeUndefined()
    expect(buildSnapshot(S).active.startSet).toBeUndefined()
  })
  it('follows the watch recording on and off', () => {
    let st = {}
    const store = { setState: p => { st = { ...st, ...p } } }
    recordingFromWatch({ on: true, entryIdx: 0, setIdx: 1, at: 5 }, store)
    expect(st.watchRec).toEqual({ entryIdx: 0, setIdx: 1, at: 5 })
    recordingFromWatch({ on: false, entryIdx: 0, setIdx: 1 }, store)
    expect(st).toEqual({ watchRec: null, watchStart: null })
  })
})
