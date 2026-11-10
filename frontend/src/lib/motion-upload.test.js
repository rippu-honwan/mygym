import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.fn()
vi.mock('./api.js', () => ({ api: (...a) => api(...a) }))
const { uploadMotion } = await import('./motion-upload.js')

function fakePlugin (files) {
  const left = { ...files }
  return {
    left,
    listMotion: vi.fn(async () => ({ names: Object.keys(left).sort() })),
    readMotion: vi.fn(async ({ name }) => ({ csv: left[name] })),
    deleteMotion: vi.fn(async ({ name }) => { delete left[name] }),
  }
}

beforeEach(() => api.mockReset())

describe('the watch motion files on their way to the server', () => {
  it('uploads each file oldest first and deletes it only once the server took it', async () => {
    const p = fakePlugin({ 'b_s2.csv': '# {}\nb', 'a_s1.csv': '# {}\na' })
    api.mockResolvedValue({ ok: true })
    expect(await uploadMotion(p)).toBe(2)
    expect(api.mock.calls.map(c => JSON.parse(c[1].body).name)).toEqual(['a_s1.csv', 'b_s2.csv'])
    expect(api.mock.calls[0]).toEqual(['/api/motion', { method: 'PUT', body: JSON.stringify({ name: 'a_s1.csv', csv: '# {}\na' }) }])
    expect(p.left).toEqual({})
  })

  it('keeps every file when the server cannot be reached, and stops there', async () => {
    const p = fakePlugin({ 'a_s1.csv': 'x', 'b_s2.csv': 'y' })
    api.mockRejectedValueOnce(Object.assign(new Error('offline'), { status: 0 }))
    expect(await uploadMotion(p)).toBe(0)
    expect(api).toHaveBeenCalledTimes(1)
    expect(p.deleteMotion).not.toHaveBeenCalled()
    expect(Object.keys(p.left)).toEqual(['a_s1.csv', 'b_s2.csv'])
  })

  it('keeps what it had not sent when the connection drops halfway', async () => {
    const p = fakePlugin({ 'a_s1.csv': 'x', 'b_s2.csv': 'y' })
    api.mockResolvedValueOnce({ ok: true }).mockRejectedValueOnce(new Error('gone'))
    expect(await uploadMotion(p)).toBe(1)
    expect(Object.keys(p.left)).toEqual(['b_s2.csv'])
  })

  it('runs once at a time: a second call while one runs joins it', async () => {
    const p = fakePlugin({ 'a_s1.csv': 'x' })
    api.mockResolvedValue({ ok: true })
    const [one, two] = await Promise.all([uploadMotion(p), uploadMotion(p)])
    expect([one, two]).toEqual([1, 1])
    expect(api).toHaveBeenCalledTimes(1)
  })
})
