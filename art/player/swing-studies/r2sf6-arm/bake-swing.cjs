const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {poses: original} = require('./bake-eight.cjs')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

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
const poses = [null, load, coil, original[3], original[4], through, finish, original[7], recoil]
const cellSize = 96
const output = path.resolve(__dirname, '../../../../game/assets/combat/r2sf8-swing-front-right.png')

async function main() {
  const {cells, contacts, pixels, width, height} = await buildStationaryCells(poses, poses.length)
  assert.deepEqual([width, height], [864, 96])
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, 9)
  assert(contacts.every(({left, right}) => left && right), 'hands hold the parcel and bat')
  const previous = await buildStationaryCells(original, original.length)
  for (const index of [0, 3, 4, 7]) {
    assert(cells[index].equals(previous.cells[index]), 'idle, precontact, contact, and recovery anchors')
  }
  for (const cell of cells) {
    for (let i = 0; i < cellSize; i++) {
      for (const pixel of [i, cellSize * (cellSize - 1) + i, cellSize * i, cellSize * (i + 1) - 1]) {
        assert.equal(cell[pixel * 4 + 3], 0, 'cell edge clips sprite')
      }
    }
  }
  if (process.argv.includes('--check')) {
    const actual = await sharp(await fs.readFile(output)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [width, height])
    assert(actual.data.equals(pixels), 'game sheet matches the authored swing')
  } else {
    await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(output)
  }
  console.log(output)
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1 })
module.exports = {poses}
