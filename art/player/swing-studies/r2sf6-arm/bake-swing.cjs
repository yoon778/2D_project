const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {poses: original} = require('./bake-eight.cjs')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

const load = {
  ...original[1],
  right: [[34,43],[24,50],[27,48]], grip: [29,46], tip: [13,36]
}
const coil = {
  ...original[2],
  right: [[38,41],[29,48],[31,42]], grip: [32,39], tip: [19,25]
}
const lead = {
  ...original[3],
  shoulder: [41,40], right: [[41,40],[39,46],[43,41]], grip: [46,39], tip: [37,21]
}
const drive = {
  ...original[3],
  head: [-2,-1,1], shoulder: [44,39],
  right: [[44,39],[55,40],[59,26]], grip: [62,23], tip: [70,6]
}
const release = {
  ...original[4],
  head: [3,0,0], shoulder: [45,39],
  torso: [[39,44],[44,38],[49,35],[55,35],[58,39],[59,45],[60,51],[56,57],[50,60],[44,57]],
  right: [[45,39],[55,41],[62,27]], grip: [65,24], tip: [84,20]
}
const contact = {
  ...original[4],
  head: [7,1,1], pack: [43,42], shoulder: [47,39],
  torso: [[40,44],[46,38],[51,35],[57,36],[61,41],[62,46],[62,51],[58,57],[52,60],[45,57]],
  chest: [[46,39],[52,37],[58,39],[60,45],[58,51],[48,54],[43,48]],
  belt: [[44,54],[51,56],[61,52],[60,56],[54,61],[45,58]],
  legs: [[[52,58],[51,66],[46,74]],[[57,57],[62,64],[56,73]]],
  right: [[47,39],[54,44],[58,40]], grip: [61,39], tip: [78,49],
  left: [[55,42],[59,48],[61,54]], parcel: [55,50], carry: [61,56]
}
const pass = {
  ...original[5],
  head: [5,3,1], shoulder: [45,41],
  legs: [[[49,59],[48,66],[46,74]],[[55,58],[60,65],[56,73]]],
  right: [[45,41],[51,42],[55,43]], grip: [54,45], tip: [57,64]
}
const cross = {
  ...original[5],
  head: [2,4,0], shoulder: [43,41],
  right: [[43,41],[50,46],[47,48]], grip: [44,46], tip: [31,61]
}
const rise = {
  ...original[7],
  head: [0,4,-2],
  shoulder: [42,43], right: [[42,43],[35,49],[31,44]], grip: [30,41], tip: [11,40]
}
const finish = {
  ...original[7],
  head: [-2,2,-2],
  shoulder: [41,43], right: [[41,43],[34,43],[29,36]], grip: [28,33], tip: [13,21]
}
const lower = {
  ...original[7],
  head: [-1,2,-1],
  shoulder: [40,42], right: [[40,42],[33,45],[29,42]], grip: [28,40], tip: [10,35]
}
const lowerToHip = {
  ...original[7],
  right: [[39,43],[33,48],[33,53]], grip: [33,56], tip: [18,68]
}
const recoil = {
  ...contact,
  head: [5,2,1], shoulder: [45,40],
  right: [[45,40],[50,44],[54,45]], grip: [55,46], tip: [69,59]
}
const retract = {
  ...original[6],
  shoulder: [41,44], right: [[41,44],[43,50],[46,49]], grip: [47,51], tip: [56,68]
}
const returnToSide = {
  ...original[7],
  right: [[39,43],[35,50],[39,52]], grip: [41,54], tip: [45,73]
}
const settle = {
  ...original[7],
  right: [[39,43],[35,50],[38,55]], grip: [40,57], tip: [37,76]
}
const poses = [
  null, load, coil, lead, drive, release, contact,
  pass, cross, rise, finish, lower, lowerToHip, original[7],
  recoil, retract, returnToSide, settle
]
const cellSize = 96
const output = path.resolve(__dirname, '../../../../game/assets/combat/r2sf8-swing-front-right.png')

async function main() {
  const {cells, contacts, pixels, width, height} = await buildStationaryCells(poses, poses.length)
  assert.deepEqual([width, height], [1728, 96])
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, poses.length)
  assert(contacts.every(({left, right}) => left && right), 'hands hold the parcel and bat')
  const previous = await buildStationaryCells(original, original.length)
  for (const [index, oldIndex] of [[0, 0], [13, 7]]) {
    assert(cells[index].equals(previous.cells[oldIndex]), 'idle and recovery anchors')
  }
  for (const pose of poses.slice(1)) {
    const [, elbow, wrist] = pose.right
    assert(Math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1]) >= 3, 'visible forearm')
    assert.deepEqual(pose.feet, original[4].feet, 'planted feet through the stationary swing')
  }
  const swingAngles = poses.slice(2,10).map(({grip, tip}) =>
    Math.atan2(tip[1] - grip[1], tip[0] - grip[0]))
  for (const [index, angle] of swingAngles.slice(1).entries()) {
    const change = (angle - swingAngles[index] + 2 * Math.PI) % (2 * Math.PI)
    assert(change > 0 && change < Math.PI / 3, 'swing follows one continuous arc')
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
