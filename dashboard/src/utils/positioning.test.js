// node --test (run by scripts/check.sh). World y points north; SVG y grows down.
import test from 'node:test'
import assert from 'node:assert/strict'
import { gridToSvg, svgToGrid } from './positioning.js'

test('larger world y is drawn higher (smaller SVG y)', () => {
  const north = gridToSvg(5, 10, 600, 600)
  const south = gridToSvg(5, 0, 600, 600)
  assert.ok(north.py < south.py)
  assert.equal(north.py, 0)
  assert.equal(south.py, 600)
  assert.equal(gridToSvg(10, 5, 600, 600).px, 600) // x is not flipped
})

test('svgToGrid inverts gridToSvg', () => {
  const { px, py } = gridToSvg(2.5, 7, 400, 300)
  assert.deepEqual(svgToGrid(px, py, 400, 300), { x: 2.5, y: 7 })
})
