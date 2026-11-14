import { describe, expect, it } from 'vitest'
import { velFrom } from './watch-sync.js'

describe('the set speed from the watch (MyGym)', () => {
  it('keeps a whole one', () => {
    expect(velFrom({ vel: { best: 1.2, last: 0.8, loss: 0.333 } })).toEqual({ vel: { best: 1.2, last: 0.8, loss: 0.333 } })
  })
  it('drops what does not hold up', () => {
    expect(velFrom({})).toEqual({})
    expect(velFrom({ vel: { best: 1, last: 0.5 } })).toEqual({})
    expect(velFrom({ vel: { best: 0, last: 0, loss: 0 } })).toEqual({})
    expect(velFrom({ vel: { best: 1, last: 0.5, loss: 1.5 } })).toEqual({})
  })
})

describe('the set raw data from the watch (MyGym)', async () => {
  const { rawFrom } = await import('./watch-sync.js')
  it('keeps a start before the tick and the checked flag', () => {
    expect(rawFrom({ startedAt: 1000, at: 61000, checked: true })).toEqual({ startedAt: 1000, checked: true })
  })
  it('drops a start after the tick or hours before it', () => {
    expect(rawFrom({ startedAt: 9000, at: 1000 })).toEqual({})
    expect(rawFrom({ startedAt: 1, at: 7200e3 })).toEqual({})
    expect(rawFrom({ checked: 'yes' })).toEqual({})
  })
})
