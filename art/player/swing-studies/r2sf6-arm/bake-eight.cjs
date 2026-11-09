const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const source = require('./pose-source.json')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

const prep = {
  head: [-2,3,0],
  pack: [35,41],
  torso: [[32,44],[37,38],[43,35],[50,36],[55,41],[57,48],[53,55],[46,59],[38,57],[34,51]],
  chest: [[38,39],[45,38],[52,41],[54,47],[50,52],[39,53],[35,48]],
  belt: [[36,53],[43,55],[54,53],[53,57],[45,60],[37,58]],
  legs: [[[42,57],[39,66],[46,74]],[[50,57],[54,66],[56,73]]],
  feet: [[46,74],[56,73]],
  shoulder: [38,41],
  right: [[38,41],[29,49],[29,50]],
  grip: [30,50],
  tip: [33,31],
  left: [[50,41],[54,46],[57,52]],
  parcel: [51,48],
  carry: [57,54],
  rightCloth: "42495f",
  rightHighlight: "555d77"
}
const recover = {
  head: [3,4,1],
  pack: [39,43],
  torso: [[36,45],[41,39],[48,37],[55,38],[60,44],[62,51],[58,57],[51,61],[43,60],[38,54]],
  chest: [[42,41],[50,40],[57,44],[59,50],[53,55],[43,56],[39,50]],
  belt: [[39,54],[47,57],[58,54],[57,58],[50,61],[41,59]],
  legs: [[[46,58],[44,66],[46,74]],[[53,57],[56,65],[56,73]]],
  feet: [[46,74],[56,73]],
  shoulder: [41,44],
  right: [[41,44],[41,52],[44,57]],
  grip: [46,59],
  tip: [48,79],
  left: [[55,43],[61,48],[61,54]],
  parcel: [56,51],
  carry: [62,57],
  rightCloth: "42495f",
  rightHighlight: "555d77"
}
const poses = [null, source[0], prep, source[1], source[2], source[3], recover, source[4]]
const output = path.resolve(__dirname, '../../../../game/assets/combat/r2sf8-arm-attack-front-right.png')

async function main() {
  const original = await buildStationaryCells([null, ...source], 6)
  const {cells, contacts, pixels, width, height} = await buildStationaryCells(poses, 8)
  assert.deepEqual([width, height], [768, 96])
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, 8)
  assert(contacts.every(({left, right}) => left && right), 'parcel and bat contact')
  const preserved = [0, 1, 3, 4, 5, 7]
  assert(original.cells.every((cell, i) => cell.equals(cells[preserved[i]])), 'original poses')
  if (process.argv.includes('--check')) {
    const actual = await sharp(output).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [width, height])
    assert(actual.data.equals(pixels), 'eight-pose game sheet matches the source')
  } else {
    await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(output)
  }
  console.log(output)
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1 })
module.exports = {poses}
