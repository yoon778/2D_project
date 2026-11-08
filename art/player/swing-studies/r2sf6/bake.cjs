const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const source = require('./pose-source.json')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

const size = 96
const game = process.argv.includes('--game')
const study = path.join(__dirname, 'poses.png')
const output = game ? path.resolve(__dirname, '../../../../game/assets/combat/r2sf6-attack-front-right.png') : study
const review = path.resolve(__dirname, '../../../../output/review', game ? 'R2-SF6-game' : 'R2-SF6-art')
const colors = cell => new Set(Array.from({length: cell.length / 4}, (_, i) => cell.readUInt32BE(i * 4)))

function connected(cell) {
  const pixels = new Set()
  for (let i = 0; i < cell.length / 4; i++) if (cell[i * 4 + 3]) pixels.add(i)
  const first = pixels.values().next().value
  const queue = [first]
  pixels.delete(first)
  for (const pixel of queue) {
    const x = pixel % size, y = Math.floor(pixel / size)
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (x + dx < 0 || x + dx >= size || y + dy < 0 || y + dy >= size) continue
      const next = (y + dy) * size + x + dx
      if (pixels.delete(next)) queue.push(next)
    }
  }
  return pixels.size === 0
}

async function main() {
  const overrides = game ? require('./runtime-pose-overrides.json') : {}
  const poses = source.map((pose, index) => ({...pose, ...overrides[index + 1]}))
  const {cells, contacts, pixels, width, height} = await buildStationaryCells([null, ...poses], 6)
  assert.deepEqual([width, height, cells.length], [576, 96, 6])
  const approved = colors(cells[0])
  const bootRows = [[80, 42, 51], [79, 52, 62]]
  for (const [i, cell] of cells.entries()) {
    assert(connected(cell), 'disconnected pixels in frame ' + i)
    for (const color of colors(cell)) assert(approved.has(color), 'approved palette and alpha')
    for (const [y, x1, x2] of bootRows) {
      const from = (y * size + x1) * 4, to = (y * size + x2 + 1) * 4
      assert(cell.subarray(from, to).equals(cells[0].subarray(from, to)), 'boot sole')
    }
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      if (x === 0 || x === size - 1 || y === 0 || y === size - 1) {
        assert.equal(cell[(y * size + x) * 4 + 3], 0, 'cell edge')
      }
    }
  }
  assert.equal(contacts.length, 5)
  assert(contacts.every(({right, left}) => right && left), 'right grip and left parcel contact')
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, 6)
  if (game) {
    const original = await sharp(study).ensureAlpha().raw().toBuffer()
    const changed = new Set()
    for (let p = 0; p < pixels.length; p += 4) {
      if (pixels.readUInt32LE(p) !== original.readUInt32LE(p)) changed.add(Math.floor((p / 4 % width) / size))
    }
    assert.deepEqual([...changed].sort((a, b) => a - b), [2, 3], 'only rotation and hit differ from the approved study')
  }
  const png = await sharp(pixels, {raw: {width, height, channels: 4}}).png().toBuffer()
  await fs.mkdir(review, {recursive: true})
  await sharp(png).resize(width * 2, height * 2, {kernel:'nearest'})
    .flatten({background:'#43535c'}).png().toFile(path.join(review, 'final-filmstrip.png'))
  if (process.argv.includes('--preview')) {
    await fs.writeFile(path.join(review, 'poses-preview.png'), png)
  } else if (process.argv.includes('--check')) {
    const actual = await sharp(output).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [width, height])
    assert(actual.data.equals(pixels), 'study reproducibility')
  } else {
    await fs.writeFile(output, png)
  }
  const tips = poses.map(pose => pose.tip)
  const steps = tips.slice(1).map(([x, y], i) => Math.hypot(x - tips[i][0], y - tips[i][1]))
  console.log(JSON.stringify({width, height, pivot:[48,80], contacts, tips, steps}))
}
main().catch(error => {console.error(error);process.exitCode=1})
