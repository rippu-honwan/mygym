// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { snapLine } from './sync-log.js'

describe('the sync log (MyGym)', () => {
  it('says a snapshot in a few words', () => {
    const snap = { active: { id: 'w1', cur: 1, rest: { endsAt: 1 }, startSet: { entryIdx: 1, setIdx: 2, at: 3 },
      entries: [{ sets: [{ done: true }, { done: true }] }, { sets: [{ done: true }, { done: false }, { done: false }] }] } }
    expect(snapLine(snap)).toBe('snap -> w=w1 cur=1 [0:2/2 1:1/3] rest=on start=e1s2')
    expect(snapLine({ active: null })).toBe('snap -> no workout')
  })
})
