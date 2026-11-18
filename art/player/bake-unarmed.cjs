// Bake the delivery courier's unarmed walk, sprint and punch from the approved rigs.
const assert = require('node:assert/strict')
const path = require('node:path')
const sharp = require('sharp')
const {renderWalkAtlas, renderSprintAtlas} = require('./consistent-walk.cjs')
const {gait} = require('./bake-sprint.cjs')
const {build, atlas} = require('./r2c8-combat-assets.cjs')
const {buildStationaryCells} = require('./r2sf-front-right.cjs')
const {poses} = require('./swing-studies/r2sf6-arm/bake-swing.cjs')
const player = require('../../game/assets/player/r1b-courier-atlas-20261104.json')
const combat = require('../../game/assets/combat/r2a-combat-20261106.json')

const assets = path.resolve(__dirname, '../../game/assets')
const parcelHidden = new Set(['back', 'back_right'])

async function write(directory, source, pixels, empty, check) {
  const [width, height] = source.canvas_size
  const suffix = empty ? '-unarmed-empty.png' : '-unarmed.png'
  const filename = path.join(assets, directory, source.image.replace(/\.png$/, suffix))
  assert.equal(pixels.length, width * height * 4, filename)
  if (check) {
    const actual = await sharp(filename).ensureAlpha().raw().toBuffer()
    assert(pixels.equals(actual), filename)
  } else {
    await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(filename)
  }
}

async function main() {
  const check = process.argv.includes('--check')
  for (const [facing, frames] of Object.entries(player.frames)) {
    for (const empty of parcelHidden.has(facing) ? [false] : [false, true]) {
      const options = {empty, unarmed: true}
      const walk = await renderWalkAtlas(facing, undefined, options)
      const sprint = await renderSprintAtlas(facing, gait, empty, {unarmed: true})
      const punchSource = combat[`attack_stationary_${facing}`]
      let cells, punch
      if (facing === 'front_right') {
        const punchPoses = [...poses]
        const contact = punchPoses[6]
        punchPoses[6] = {...contact, right: [contact.shoulder, [54, 46], [64, 44]], grip: [67, 43]}
        const result = await buildStationaryCells(punchPoses, punchPoses.length, {empty, unarmedWalk: walk})
        cells = result.cells
        punch = result.pixels
      } else {
        const result = await build(facing, walk, {...options, horizontalSwing: true})
        cells = result.stationary
        punch = atlas(cells, cells.length).b
      }
      assert(cells[0].equals(cells[13]), facing + ' punch recovery must match idle')
      assert(!cells[6].equals(cells[0]), facing + ' punch contact must move the arm')
      await write('player', player.sources[frames[0].source], walk, empty, check)
      await write('player', {...player.sprint, image: player.sprint.images[facing]}, sprint.pixels, empty, check)
      await write('combat', punchSource, punch, empty, check)
    }
    console.log(`${facing}: unarmed idle, walk, sprint and punch`)
  }
}

main().catch(error => {console.error(error); process.exitCode = 1})
