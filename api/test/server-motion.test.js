/* The rep counter's motion files (docs/dev/rep-counter.md): the paired phone uploads one CSV per
   set, stored as sent in DATA_DIR/motion/<uid>/. Signed-in only, a strict name, each profile in
   its own folder. Real server.js in a child. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { boundPort } from './helpers.mjs';

const API = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const SECRET = crypto.randomBytes(32).toString('hex');
function mintSession(uid, sv = 0) {
  const payload = `${uid}:${Date.now() + 86400000}:${sv}`;
  return payload + '.' + crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');
}
const USERS = [
  { id: 'u_m_1', name: 'One', created: new Date().toISOString() },
  { id: 'u_m_2', name: 'Two', created: new Date().toISOString() }
];

async function startServer(t) {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'gym-motion-'));
  fs.writeFileSync(path.join(dataDir, 'secret'), SECRET, { mode: 0o600 });
  fs.writeFileSync(path.join(dataDir, 'db.json'), JSON.stringify({ users: USERS, creds: [], subs: [], invites: [] }));
  const child = spawn(process.execPath, ['server.js'], {
    cwd: API, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PORT: '0', DATA_DIR: dataDir, ORIGIN: 'http://localhost:8080', RP_ID: 'localhost' }
  });
  const h = { log: '', dataDir };
  child.stdout.on('data', d => h.log += d);
  child.stderr.on('data', d => h.log += d);
  t.after(() => { child.kill('SIGKILL'); fs.rmSync(dataDir, { recursive: true, force: true }); });
  h.api = `http://127.0.0.1:${await boundPort(child, () => h.log)}`;
  return h;
}

const NAME = '20261111-045641_0025_s1.csv';
const CSV = '# {"exId":"0025","reps":8}\nt,ax,ay,az,rx,ry,rz,gx,gy,gz\n0.000,0.1,0,0,0,0,0,0,0,-1\n';

test('the phone uploads a set\'s motion file into its own folder', async t => {
  const h = await startServer(t);
  const put = (body, uid) => fetch(h.api + '/api/motion', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(uid ? { Authorization: `Bearer ${mintSession(uid)}` } : {}) },
    body: JSON.stringify(body),
  });
  const file = (uid, name) => path.join(h.dataDir, 'motion', uid, name);

  assert.equal((await put({ name: NAME, csv: CSV })).status, 401, 'not signed in');

  const r = await put({ name: NAME, csv: CSV }, 'u_m_1');
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true });
  assert.equal(fs.readFileSync(file('u_m_1', NAME), 'utf8'), CSV);

  // the same set sent again: replaced, not duplicated
  const again = CSV + '0.020,0.2,0,0,0,0,0,0,0,-1\n';
  assert.equal((await put({ name: NAME, csv: again }, 'u_m_1')).status, 200);
  assert.equal(fs.readFileSync(file('u_m_1', NAME), 'utf8'), again);
  assert.deepEqual(fs.readdirSync(path.join(h.dataDir, 'motion', 'u_m_1')), [NAME]);

  // another profile: its own folder
  assert.equal((await put({ name: NAME, csv: CSV }, 'u_m_2')).status, 200);
  assert.equal(fs.readFileSync(file('u_m_2', NAME), 'utf8'), CSV);
  assert.equal(fs.readFileSync(file('u_m_1', NAME), 'utf8'), again);

  for (const bad of ['../x.csv', '../../db.json', 'a.csv', '20261111-045641_0025_s1.txt', '20261111-045641_../x_s1.csv', '', 5]) {
    assert.equal((await put({ name: bad, csv: CSV }, 'u_m_1')).status, 400, `name ${JSON.stringify(bad)}`);
  }
  for (const bad of ['t,ax\n0,1\n', 42, null]) {
    assert.equal((await put({ name: NAME, csv: bad }, 'u_m_1')).status, 400, `csv ${JSON.stringify(bad)}`);
  }
  assert.equal(fs.existsSync(path.join(h.dataDir, 'x.csv')), false);
});
