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
