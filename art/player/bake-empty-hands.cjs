// Offline baker. The shipped game only loads the baked PNGs.
const assert = require('node:assert/strict')
const path = require('node:path')
const sharp = require('sharp')
const {build} = require('./r2c8-combat-assets.cjs')
const {buildFullSwing, buildMovingFullSwing, buildStationaryCells} = require('./r2sf-front-right.cjs')
const {poses} = require('./swing-studies/r2sf6-arm/bake-swing.cjs')
const {removeWalkParcels} = require('./empty-hands.cjs')
const {bodyDrop} = require('./consistent-rig.json')
const player = require('../../game/assets/player/r1b-courier-atlas-20261104.json')
const combat = require('../../game/assets/combat/r2a-combat-20261106.json')
const assets = path.resolve(__dirname, '../../game/assets')
const options = {empty: true}

async function writeVariant(directory, source, pixels) {
  const [width, height] = source.canvas_size
  assert.equal(pixels.length, width * height * 4)
  const file = path.join(assets, directory, source.image.replace(/\.png$/, '-empty.png'))
  if (process.argv.includes('--check')) {
    const actual = await sharp(file).ensureAlpha().raw().toBuffer()
    assert(pixels.equals(actual), file)
  } else {
    await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(file)
  }
}

function packCells(cells, columns) {
  const side = 96
  const width = columns * side
  const pixels = Buffer.alloc(width * Math.ceil(cells.length / columns) * side * 4)
  for (const [index, cell] of cells.entries()) {
    for (let y = 0; y < side; y++) {
      const dest = ((Math.floor(index / columns) * side + y) * width + index % columns * side) * 4
      cell.copy(pixels, dest, y * side * 4, (y + 1) * side * 4)
    }
  }
  return pixels
}

async function main() {
  for (const facing of ['front_right', 'front', 'front_left', 'left', 'right', 'back_left']) {
    const source = player.sources[player.frames[facing][0].source]
    const atlas = await sharp(path.join(assets, 'player', source.image)).ensureAlpha().raw().toBuffer()
    await writeVariant('player', source, removeWalkParcels(facing, atlas, bodyDrop))
    if (facing !== 'front_right') {
      const result = await build(facing, atlas, options)
      await writeVariant('combat', result.attack, packCells(result.stationary, 4))
      await writeVariant('combat', result.attack_walk, packCells(result.moving, 8))
    }
  }
  await writeVariant('combat', combat.attack, (await buildFullSwing(options)).pixels)
  await writeVariant('combat', combat.attack_walk, (await buildMovingFullSwing(options)).pixels)
  await writeVariant('combat', combat.attack_stationary_front_right,
    (await buildStationaryCells(poses, poses.length, options)).pixels)
  console.log('19 empty-handed atlases verified or baked')
}

main().catch(error => { console.error(error); process.exitCode = 1 })
