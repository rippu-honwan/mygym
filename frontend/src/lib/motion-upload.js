// Rep counter (docs/dev/rep-counter.md): the Apple Watch records one CSV of motion per set, the
// iPhone keeps it (WatchBridgePlugin, Documents/motion), and this sends it to the paired server
// (PUT /api/motion). A file is deleted on the phone only once the server took it; anything that
// fails stays for the next try: at launch, when a new file arrives, when the app comes back.
import { api } from './api.js'
import { MOBILE, nativePlatform } from './mobile.js'

let running = null

/** Every waiting file, oldest first; stops at the first failure (offline, not paired, the server
 *  away). Resolves with how many went up. */
// ponytail: a file the server refuses (400) blocks the ones after it; the watch only writes valid
// ones, so this is a bug signal, not a case to route around.
export function uploadMotion (plugin) {
  if (running) return running
  running = (async () => {
    let sent = 0
    try {
      const { names = [] } = await plugin.listMotion()
      for (const name of names) {
        const { csv } = await plugin.readMotion({ name })
        await api('/api/motion', { method: 'PUT', body: JSON.stringify({ name, csv }) })
        await plugin.deleteMotion({ name })
        sent++
      }
    } catch { /* kept on the phone for the next try */ }
    return sent
  })().finally(() => { running = null })
  return running
}

let started = false
/** iPhone only: the Android plugin has no motion files. */
export async function initMotionUpload () {
  if (!MOBILE || started) return
  started = true
  try {
    if ((await nativePlatform()) !== 'ios') return
    const { registerPlugin } = await import('@capacitor/core')
    const plugin = registerPlugin('WatchBridge')
    const go = () => { uploadMotion(plugin) }
    go()
    plugin.addListener('motionFile', go)
    const { App } = await import('@capacitor/app')
    App.addListener('appStateChange', ({ isActive }) => { if (isActive) go() })
  } catch { /* no native side here */ }
}
