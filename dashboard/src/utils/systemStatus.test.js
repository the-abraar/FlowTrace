// node --test (run by scripts/check.sh).
import test from 'node:test'
import assert from 'node:assert/strict'
import { systemBadge } from './systemStatus.js'

test('only the live backend shows a green "System Active" badge', () => {
  assert.equal(systemBadge('connected').label, 'System Active')
  assert.match(systemBadge('connected').box, /green/)
  for (const mode of ['connecting', 'demo', 'offline', undefined, 'bogus']) {
    const b = systemBadge(mode)
    assert.notEqual(b.label, 'System Active', String(mode))
    assert.doesNotMatch(b.box + b.dot, /green/, String(mode))
  }
  assert.equal(systemBadge('demo').label, 'Demo Data')
  assert.equal(systemBadge('offline').label, 'Offline')
})

test('before the first connect attempt ends the badge says Connecting, not Offline', () => {
  const b = systemBadge('connecting')
  assert.equal(b.label, 'Connecting')
  assert.doesNotMatch(b.box + b.dot, /red|green/)
})
