// Bake independently posed stationary swings on the approved front-right clock.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {build, atlas} = require('../r2c8-combat-assets.cjs')
const directions = require('./r10-horizontal-swing.json')

const directory = path.resolve(__dirname, '../../../game/assets/combat')
const metadataFile = path.join(directory, 'r2a-combat-20261106.json')
const cellSize = 96
const parcelHidden = new Set(['back', 'back_right'])

function validate(cells, layers) {
  assert.equal(cells.length, 18)
  assert(cells[0].equals(cells[13]), 'recovery must match idle')
  assert(cells[7].compare(cells[6]) !== 0, 'miss must pass contact')
  assert(cells[8].compare(cells[14]) !== 0, 'hit and miss recover independently')
  for (const cell of cells) {
    for (let i = 0; i < cellSize; i++) {
      for (const pixel of [i, cellSize * (cellSize - 1) + i, cellSize * i, cellSize * (i + 1) - 1]) {
        assert.equal(cell[pixel * 4 + 3], 0, 'sprite touches atlas cell edge')
      }
    }
  }
  for (const layer of layers.filter(Boolean)) {
    const {shoulder, elbow, wrist, grip, tip, arm, weapon} = layer
    assert(Math.hypot(wrist[0] - grip[0], wrist[1] - grip[1]) <= 6.1, 'grip separates from wrist')
    assert(Math.hypot(elbow[0] - shoulder[0], elbow[1] - shoulder[1]) >= 7, 'upper arm collapses')
    assert(Math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1]) >= 4, 'forearm collapses')
    assert(Math.hypot(tip[0] - grip[0], tip[1] - grip[1]) >= 18 - 1e-8, 'bat shrinks')
    const x = Math.floor(grip[0] + 8), y = Math.floor(grip[1] + 8)
    let joined = false
    for (let row = y - 3; row <= y + 3; row++) for (let col = x - 3; col <= x + 3; col++) {
      const alpha = (row * cellSize + col) * 4 + 3
      joined ||= arm[alpha] > 0 && weapon[alpha] > 0
    }
    assert(joined, 'weapon does not overlap grip pixels')
  }
  for (const index of [6, 7, 8, 14]) {
    const weapon = layers[index].weapon
    let visible = 0
    for (let p = 0; p < weapon.length; p += 4) {
      const [red, green, , alpha] = weapon.subarray(p, p + 4)
      if (alpha && red > 130 && red > green * 1.15 && cells[index].readUInt32BE(p) === weapon.readUInt32BE(p)) {
        visible++
      }
    }
    assert(visible >= 15, `bat is obscured through contact or follow-through in cell ${index}`)
  }
}

async function bake(facing, asset, check, empty) {
  const {stationary, layers} = await build(facing, null, {horizontalSwing: true, empty})
  validate(stationary, layers)
  const {b, width, height} = atlas(stationary, stationary.length)
  const file = path.join(directory, empty ? asset.replace(/\.png$/, '-empty.png') : asset)
  if (check) {
    const actual = await sharp(await fs.readFile(file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [width, height])
    assert(actual.data.equals(b), `authored pixels differ: ${file}`)
  } else {
    await sharp(b, {raw: {width, height, channels: 4}}).png().toFile(file)
  }
}

async function main() {
  const argv = process.argv.slice(2)
  const check = argv.includes('--check')
  const selected = argv.filter(value => value !== '--check')
  const facings = selected.length ? selected : Object.keys(directions)
  const source = await fs.readFile(metadataFile, 'utf8')
  const metadata = JSON.parse(source)
  const reference = metadata.attack_stationary_front_right
  for (const facing of facings) {
    assert(Object.hasOwn(directions, facing), `unknown direction ${facing}`)
    const key = `attack_stationary_${facing}`
    const image = `r10-10-swing-${facing.replaceAll('_', '-')}.png`
    const entry = {...reference, image, facing}
    await bake(facing, image, check, false)
    if (!parcelHidden.has(facing)) await bake(facing, image, check, true)
    if (check) assert.deepEqual(metadata[key], entry)
    else metadata[key] = entry
    console.log(`${facing}: ${parcelHidden.has(facing) ? '18' : '18 + 18'} poses`)
  }
  if (!check) {
    const json = JSON.stringify(metadata, null, 2) + '\n'
    await fs.writeFile(metadataFile, source.includes('\r\n') ? json.replaceAll('\n', '\r\n') : json)
  }
}

if (require.main === module) main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
