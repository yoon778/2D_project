const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {poses: original} = require('./bake-eight.cjs')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

const batLength = 20

function armed(pose, right, grip, angle) {
  const radians = angle * Math.PI / 180
  const tip = [grip[0] + Math.round(batLength * Math.cos(radians)),
    grip[1] + Math.round(batLength * Math.sin(radians))]
  return {...pose, shoulder: right[0], right, grip, tip}
}

const load = armed({...original[1], head: [-2,3,0]}, [[36,43],[27,51],[30,48]], [32,47], 161)
const coil = armed({...original[2], head: [-1,3,0]}, [[38,42],[28,50],[31,45]], [34,44], 196)
const lead = armed({...original[3], head: [-1,2,0]}, [[41,41],[34,49],[40,46]], [42,43], 228)
const drive = armed({...original[3], head: [-1,0,0]}, [[43,40],[49,49],[58,45]], [61,44], 287)
const release = armed({
  ...original[4],
  head: [4,0,1],
  torso: [[39,44],[44,38],[49,35],[55,35],[58,39],[59,45],[60,51],[56,57],[50,60],[44,57]]
}, [[45,39],[54,47],[59,44]], [62,42], 334)
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
const pass = armed({
  ...original[5],
  head: [5,2,1],
  legs: [[[49,59],[48,66],[46,74]],[[55,58],[60,65],[56,73]]]
}, [[45,41],[52,48],[57,47]], [60,46], 48)
const cross = armed({
  ...original[5],
  head: [3,3,1]
}, [[44,42],[52,47],[58,51]], [61,53], 79)
const across = armed({...original[6], head: [1,4,0]}, [[42,43],[47,49],[48,54]], [50,56], 127)
const finish = armed({...original[7], head: [0,3,0]}, [[40,43],[38,52],[36,49]], [36,47], 176)
const lower = armed({...original[7], head: [0,2,0]}, [[39,43],[34,50],[35,54]], [37,53], 143)
const lowerToHip = armed({...original[7], head: [0,1,0]}, [[39,43],[35,51],[37,55]], [39,55], 113)
const recoil = armed({
  ...contact,
  head: [5,2,1],
}, [[45,41],[49,49],[54,45]], [57,44], 24)
const retract = armed({...original[6], head: [3,3,1]}, [[43,43],[45,51],[49,49]], [52,48], 53)
const returnToSide = armed({...original[7], head: [1,3,0]}, [[41,43],[39,51],[43,53]], [46,53], 81)
const settle = armed({...original[7], head: [0,2,0]}, [[39,43],[34,51],[36,54]], [37,56], 107)
const poses = [
  null, load, coil, lead, drive, release, contact,
  pass, cross, across, finish, lower, lowerToHip, null,
  recoil, retract, returnToSide, settle
]
const cellSize = 96
const output = path.resolve(__dirname, '../../../../game/assets/combat/r2sf8-swing-front-right.png')

async function bake(file, empty) {
  const {cells, contacts, pixels, width, height} = await buildStationaryCells(poses, poses.length, {empty})
  assert.deepEqual([width, height], [1728, 96])
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, poses.length - 1)
  assert(cells[13].equals(cells[0]), 'last recovery cell matches idle exactly')
  assert(contacts.every(({left, right}) => right && (empty || left)), 'hands hold their equipment')
  for (const pose of poses.filter(Boolean)) {
    const [shoulder, elbow, wrist] = pose.right
    assert.deepEqual(pose.shoulder, shoulder, 'shoulder shares the upper arm joint')
    assert(Math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1]) >= 3, 'visible forearm')
    assert(Math.hypot(wrist[0] - pose.grip[0], wrist[1] - pose.grip[1]) <= 4, 'hand joins the forearm')
    assert(Math.abs(Math.hypot(pose.tip[0] - pose.grip[0], pose.tip[1] - pose.grip[1]) - batLength) <= .65,
      'bat length stays fixed within pixel rounding')
    assert.deepEqual(pose.feet, original[4].feet, 'planted feet through the stationary swing')
  }
  const swingAngles = poses.slice(1,11).map(({grip, tip}) =>
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
    const actual = await sharp(await fs.readFile(file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [width, height])
    assert(actual.data.equals(pixels), 'game sheet matches the authored swing')
  } else {
    await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(file)
  }
  console.log(file)
}

async function main() {
  await bake(output, false)
  await bake(output.replace(/\.png$/, '-empty.png'), true)
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1 })
module.exports = {poses}
