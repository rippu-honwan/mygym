// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { nextWatchSet } from './WatchStartBar.jsx'

// MyGym: which set the bottom Start bar starts on the watch.
describe('the next set for the watch', () => {
  const A = (id, sets, target = {}) => ({ cur: 0, entries: [{ id, target, sets }] })
  it('is the first set not done of the exercise up next', () => {
    expect(nextWatchSet(A('0577', [{ done: true }, { done: false }]))).toMatchObject({ entryIdx: 0, setIdx: 1 })
  })
  it('is none when all sets are done, for legs, or for a timed hold', () => {
    expect(nextWatchSet(A('0577', [{ done: true }]))).toBeNull()
    expect(nextWatchSet(A('0599', [{ done: false }]))).toBeNull()
    expect(nextWatchSet(A('0577', [{ done: false }], { mode: 'time' }))).toBeNull()
  })
})
