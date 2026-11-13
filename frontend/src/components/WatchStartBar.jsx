// MyGym: a big Start set bar at the bottom of the workout screen (iPhone with an Apple Watch).
// It starts the watch's recording of the next set of the exercise up next (lib/watch-sync.js
// `startSet`), and shows when the watch is recording ("recording" event). Hidden during a rest,
// where the rest bar sits; not for legs or timed holds (the watch does not count those).
import { useEffect } from 'react'
import { useStore } from '../store/useStore.js'
import { useUI } from '../store/useUI.js'
import { MOBILE } from '../lib/mobile.js'
import { readWatchPrefs, readWatchStatus } from '../lib/watch-settings.js'
import { modeOf, isPerSide } from '../lib/history.js'
import { EXIDX } from '../lib/exercises.js'
import { Button } from './ui.jsx'
import Icon from './Icon.jsx'

export function nextWatchSet(A) {
  const entryIdx = A?.cur ?? 0
  const e = A?.entries?.[entryIdx]
  if (!e || !Array.isArray(e.sets)) return null
  const cfg = { ...(e.target || {}), id: e.id }
  if (modeOf(cfg) !== 'reps' || ['upper legs', 'lower legs'].includes(EXIDX[e.id]?.bp)) return null
  const setIdx = e.sets.findIndex(s => !s.done)
  if (setIdx < 0) return null
  return { entryIdx, setIdx, perSide: isPerSide(cfg) }
}

export default function WatchStartBar() {
  const A = useStore(s => s.S.active)
  const timer = useUI(s => s.timer)
  const rec = useUI(s => s.watchRec)
  const asked = useUI(s => s.watchStart)
  const on = MOBILE && readWatchPrefs().enabled && !!readWatchStatus()?.at
  const next = on ? nextWatchSet(A) : null
  const resting = !!(timer && !timer.ready)
  const show = !!next && !resting
  useEffect(() => {
    document.body.classList.toggle('watch-start', show)
    return () => document.body.classList.remove('watch-start')
  }, [show])
  if (!show) return null
  const recording = rec && rec.entryIdx === next.entryIdx && Date.now() - rec.at < 15 * 60e3
  const waiting = !recording && asked && asked.entryIdx === next.entryIdx && Date.now() - asked.at < 5e3
  return (
    <div className="watch-start-bar">
      {recording
        ? <div className="watch-start-rec"><Icon name="watch" /><span>{`Recording set ${rec.setIdx + 1} on the watch`}</span></div>
        : <Button variant="primary" icon="watch" className="watch-start-btn"
            onClick={() => useUI.setState({ watchStart: { entryIdx: next.entryIdx, setIdx: next.setIdx, at: Date.now() } })}>
            {waiting ? 'Starting on the watch…' : `Start set ${next.setIdx + 1} on the watch`}
          </Button>}
    </div>
  )
}
