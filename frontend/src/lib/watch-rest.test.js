import { describe, expect, it, vi } from 'vitest'
import { restFromWatch } from './watch-sync.js'

// MyGym: Skip and +15 s on the watch move the phone's rest timer too.
describe('the watch rest events on the phone', () => {
  const ui = timer => ({ timer, skipRest: vi.fn(), addRest: vi.fn() })
  it('skips the running rest', () => {
    const u = ui({ endsAt: Date.now() + 60e3 })
    restFromWatch({ type: 'rest', at: 123 }, u)
    expect(u.skipRest).toHaveBeenCalledWith(123)
  })
  it('moves its end by the seconds added', () => {
    const end = Date.now() + 60e3
    const u = ui({ endsAt: end })
    restFromWatch({ type: 'rest', endsAt: end + 15e3 }, u)
    expect(u.addRest).toHaveBeenCalledWith(15)
  })
  it('leaves a finished, paused or missing rest alone', () => {
    for (const t of [null, { ready: true }, { paused: true, endsAt: Date.now() + 9e3 }]) {
      const u = ui(t)
      restFromWatch({ type: 'rest', endsAt: Date.now() + 20e3 }, u)
      expect(u.addRest).not.toHaveBeenCalled()
      if (!t || t.ready) expect(u.skipRest).not.toHaveBeenCalled()
    }
  })
})
