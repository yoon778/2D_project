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
  shoulder: [41,40], right: [[41,40],[39,48],[45,43]], grip: [48,41], tip: [39,24]
}
const drive = {
  ...original[3],
  head: [-2,-1,1],
  right: [[43,39],[56,42],[61,28]], grip: [63,25], tip: [69,7]
}
const release = {
  ...original[4],
  head: [1,0,-1],
  shoulder: [44,39], right: [[44,39],[54,42],[62,30]], grip: [65,27], tip: [81,16]
}
const pass = {
  ...original[5],
  shoulder: [44,42], right: [[44,42],[50,45],[54,48]], grip: [53,51], tip: [50,70]
}
const cross = {
  ...original[5],
  shoulder: [43,41], right: [[43,41],[48,48],[44,52]], grip: [41,51], tip: [25,62]
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
  ...original[4],
  head: [4,2,1],
  right: [[43,39],[49,47],[52,46]], grip: [53,47], tip: [66,61]
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
  null, load, coil, lead, drive, release, original[4],
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
  for (const [index, oldIndex] of [[0, 0], [6, 4], [13, 7]]) {
    assert(cells[index].equals(previous.cells[oldIndex]), 'idle, contact, and recovery anchors')
  }
  for (const pose of poses.slice(1)) {
    const [, elbow, wrist] = pose.right
    assert(Math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1]) >= 3, 'visible forearm')
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
