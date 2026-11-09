const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {poses: original} = require('./bake-eight.cjs')
const {renderWalkAtlas} = require('../../consistent-walk.cjs')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

const carryRig = {
  carryArm: {pivot: [29, 45], degrees: 24, mask: {rows: {
    46: [27,32], 47: [26,32], 48: [26,32], 49: [26,32],
    50: [26,32], 51: [26,32], 52: [27,29]
  }}},
  batMask: {rows: {
    52: [30,32], 53: [28,32],
    ...Object.fromEntries(Array.from({length: 19}, (_, i) => [54 + i, [24,32]]))
  }},
  batRotation: {pivot: [29,51], targetPivot: [26.56,50.48], degrees: 106}
}
const load = {...original[1], tip: [13, 45]}
const coil = {...original[2], tip: [22, 32]}
const through = {
  ...original[5],
  right: [[43,45],[47,51],[47,57]],
  grip: [45,59],
  tip: [34,75]
}
const finish = {
  ...original[7],
  head: [0,4,-2],
  shoulder: [41,43],
  right: [[41,43],[46,50],[39,51]],
  grip: [36,51],
  tip: [18,46]
}
const recoil = {
  ...original[6],
  shoulder: [41,44],
  right: [[41,44],[43,52],[47,52]],
  grip: [49,52],
  tip: [62,66]
}
const settle = {
  ...original[7],
  right: [[39,43],[36,51],[38,55]],
  grip: [36,57],
  tip: [18,50]
}
const poses = [null, load, coil, original[3], original[4], through, finish, settle, recoil]
const cellSize = 96
const assets = path.resolve(__dirname, '../../../../game/assets')
const output = path.join(assets, 'combat/r2sf8-swing-front-right.png')
const carryOutput = path.join(assets, 'player/r1-consistent-front-right-ready.png')

async function writeOrCheck(file, pixels, width, height, check) {
  if (check) {
    const actual = await sharp(await fs.readFile(file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [width, height])
    assert(actual.data.equals(pixels), file + ' matches the bake')
  } else {
    await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(file)
  }
}

async function main() {
  const check = process.argv.includes('--check')
  const carry = await renderWalkAtlas('front_right', carryRig)
  await writeOrCheck(carryOutput, carry, 320, 240, check)
  const {cells, contacts, pixels, width, height} = await buildStationaryCells(poses, poses.length, carryOutput)
  assert.deepEqual([width, height], [864, 96])
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, 9)
  assert(contacts.every(({left, right}) => left && right), 'hands hold the parcel and bat')
  const previous = await buildStationaryCells(original, original.length)
  for (const index of [3, 4]) {
    assert(cells[index].equals(previous.cells[index]), 'precontact and contact art')
  }
  for (const cell of cells) {
    for (let i = 0; i < cellSize; i++) {
      for (const pixel of [i, cellSize * (cellSize - 1) + i, cellSize * i, cellSize * (i + 1) - 1]) {
        assert.equal(cell[pixel * 4 + 3], 0, 'cell edge clips sprite')
      }
    }
  }
  await writeOrCheck(output, pixels, width, height, check)
  console.log(output)
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1 })
module.exports = {poses, carryOutput}
