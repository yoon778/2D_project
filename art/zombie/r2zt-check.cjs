const assert = require('node:assert/strict')
const {execFileSync} = require('node:child_process')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {atlas, facings} = require('./raster.cjs')
const {corpse, loadStates} = require('./r2z-zombie-assets.cjs')
const {bodyDrop} = require('../player/consistent-rig.json')

const root = path.resolve(__dirname, '../..')
const baseline = 'b6a0a0f'
const asset = 'game/assets/zombie/r2z-zombie-20261106'
const review = path.join(root, 'output/review/R2-ZT-art')
const size = 80
const width = 640

function git(...args) {
  return execFileSync('git', args, {cwd: root})
}

function readCell(pixels, [left, top]) {
  const cell = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y++) {
    const from = ((top + y) * width + left) * 4
    pixels.copy(cell, y * size * 4, from, from + size * 4)
  }
  return cell
}

function checkCell(frame, cell, palette) {
  const mask = new Uint8Array(size * size)
  for (const [row, spans] of Object.entries(frame.opaque_rows)) {
    const y = Number(row)
    assert(Number.isInteger(y) && y >= 0 && y < size)
    let previous = -2
    for (const [left, right] of spans) {
      assert(Number.isInteger(left) && Number.isInteger(right))
      assert(left > previous + 1 && left <= right && right < size)
      mask.fill(1, y * size + left, y * size + right + 1)
      previous = right
    }
  }
  let area = 0
  for (let p = 0; p < mask.length; p++) {
    const offset = p * 4
    assert.equal(cell[offset + 3], mask[p] * 255)
    if (!mask[p]) continue
    const x = p % size, y = Math.floor(p / size)
    assert(x > 0 && x < size - 1 && y > 0 && y < size - 1, 'cell boundary contact')
    assert(palette.has(cell.toString('hex', offset, offset + 3)), 'new palette color')
    area++
  }
  assert(area > 0)
  const start = mask.indexOf(1)
  const queue = [start]
  mask[start] = 0
  for (let i = 0; i < queue.length; i++) {
    const p = queue[i]
    // Boundary pixels have already been excluded.
    for (const offset of [-81, -80, -79, -1, 1, 79, 80, 81]) {
      if (!mask[p + offset]) continue
      mask[p + offset] = 0
      queue.push(p + offset)
    }
  }
  assert.equal(queue.length, area, 'detached sprite pixels')
}

function checkUpper(cell, upper, drop) {
  for (let p = 0; p < size * (size - drop) * 4; p += 4) {
    if (upper[p + 3]) assert.equal(cell.readUInt32LE(p + drop * size * 4), upper.readUInt32LE(p))
  }
}

function pixelChanges(from, to) {
  let rgba = 0, alpha = 0
  for (let p = 0; p < from.length; p += 4) {
    if (from.readUInt32LE(p) !== to.readUInt32LE(p)) rgba++
    if (from[p + 3] !== to[p + 3]) alpha++
  }
  return {rgba, alpha}
}

async function main() {
  const pngPath = path.join(root, asset + '.png')
  const jsonPath = path.join(root, asset + '.json')
  const [png, json] = await Promise.all([fs.readFile(pngPath), fs.readFile(jsonPath)])
  const metadata = JSON.parse(json)
  const current = await sharp(png).ensureAlpha().raw().toBuffer({resolveWithObject: true})
  assert.deepEqual([current.info.width, current.info.height], [width, 2400])
  assert.deepEqual(metadata.canvas_size, [width, 2400])
  const original = await sharp(git('show', `${baseline}:${asset}.png`)).ensureAlpha().raw().toBuffer()
  assert.equal(original.length, width * 1120 * 4)
  assert(current.data.subarray(0, original.length).equals(original), 'legacy atlas RGBA')
  const legacyMetadata = structuredClone(metadata)
  legacyMetadata.canvas_size = [width, 1120]
  for (const facing of facings) delete legacyMetadata.facings[facing].resume
  assert.deepEqual(legacyMetadata, JSON.parse(git('show', `${baseline}:${asset}.json`)))
  assert.equal(git('diff', '--name-only', baseline, '--', 'art/zombie', 'art/player', 'game/assets',
    ':(exclude)art/zombie/r2z-zombie-assets.cjs', ':(exclude)art/zombie/raster.cjs',
    ':(exclude)art/zombie/r2zt-check.cjs', `:(exclude)${asset}.png`, `:(exclude)${asset}.json`).length, 0)

  const palette = new Set()
  for (let p = 0; p < original.length; p += 4) {
    if (original[p + 3]) palette.add(original.toString('hex', p, p + 3))
  }
  assert.equal(palette.size, 24)
  const states = await loadStates()
  const changes = {}
  for (const [col, facing] of facings.entries()) {
    const {idle, walk, resume} = metadata.facings[facing]
    assert.equal(resume.length, 8)
    changes[facing] = resume.map((frames, phase) => {
      assert.equal(frames.length, 2)
      const poses = frames.map((frame, step) => {
        const top = size * (14 + 2 * phase + step)
        assert.deepEqual(frame.clip_topleft, [col * size, top, size, size])
        assert.deepEqual(frame.foot_pivot_topleft, [col * size + 40, top + 72])
        const cell = readCell(current.data, frame.clip_topleft)
        checkCell(frame, cell, palette)
        checkUpper(cell, states[facing].upper, step * bodyDrop[phase])
        return cell
      })
      const first = readCell(current.data, idle.clip_topleft)
      const last = readCell(current.data, walk[phase].clip_topleft)
      const chain = [first, ...poses, last]
      const direct = pixelChanges(first, last)
      const steps = chain.slice(1).map((pose, i) => pixelChanges(chain[i], pose))
      for (const step of steps) {
        assert(step.alpha < direct.alpha && step.rgba < direct.rgba, `${facing} walk ${phase}`)
      }
      return {direct, steps}
    })
  }

  const recreated = atlas(states, corpse(states.front_right))
  assert.deepEqual(recreated.metadata, metadata)
  const reproducedPng = await sharp(recreated.pixels, {
    raw: {width: recreated.width, height: recreated.height, channels: 4},
  }).png().toBuffer()
  assert(reproducedPng.equals(png), 'reproduced PNG bytes')
  assert((await fs.readFile(pngPath)).equals(png))
  assert((await fs.readFile(jsonPath)).equals(json))
  const report = {baseline, legacyCells: 105, attackCellsPreserved: 96, resumeCells: 128,
    palette: palette.size, checkedMaskPixels: 128 * size * size, improvedTransitions: 64,
    productWrites: 0, changes}
  await fs.mkdir(review, {recursive: true})
  await fs.writeFile(path.join(review, 'asset-check.json'), JSON.stringify(report, null, 2) + '\n')
  const {changes: _, ...summary} = report
  console.log(JSON.stringify(summary))
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
