// Offline bake of eight sprint directions using the approved courier parts.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {renderSprintAtlas} = require('./consistent-walk.cjs')

const cell = 80
const width = 4 * cell, height = 2 * cell
const raw = {width, height, channels: 4}
const root = path.resolve(__dirname, '../..')
const assets = path.join(root, 'game/assets/player')
const review = path.join(root, 'output/review/R8-D')
const facings = ['front_right', 'right', 'back_right', 'back', 'back_left', 'left', 'front_left', 'front']
const occludedParcel = new Set(['back', 'back_right'])

// Three flat-foot contacts, then toe-off and a higher swing. The other leg
// follows four samples later. 8 native px 횞 1.5 display scale = 12 world px.
const gait = {
  strideNative: [12, 4, -4, -12, -15, -9, 3, 10],
  swingLift: [0, 0, 0, 2, 7, 10, 8, 4],
  kneeForward: [1, 3, 2, 0, 2, 7, 8, 4],
  bootPitchDegrees: [0, 0, 0, 13, 22, -14, -9, -5],
  bodyDrop: [0, 2, 1, -1, 0, 2, 1, -1],
  bodyLean: 0.085,
}

function extractFrame(index) {
  return {left: index % 4 * cell, top: Math.floor(index / 4) * cell, width: cell, height: cell}
}

async function frames(pixels) {
  return Promise.all(Array.from({length: 8}, (_, index) =>
    sharp(pixels, {raw}).extract(extractFrame(index)).raw().toBuffer()))
}

async function writeReview(held, empty, destination) {
  const rows = [...await frames(held), ...await frames(empty)]
  const frameSize = cell * 3
  const strips = await Promise.all(rows.map(frame =>
    sharp(frame, {raw: {width: cell, height: cell, channels: 4}})
      .resize(frameSize, frameSize, {kernel: 'nearest'}).png().toBuffer()))
  await fs.mkdir(destination, {recursive: true})
  await sharp({create: {width: frameSize * 8, height: frameSize * 2, channels: 4, background: '#3b444c'}})
    .composite(strips.map((input, index) => ({
      input, left: index % 8 * frameSize, top: Math.floor(index / 8) * frameSize,
    }))).png().toFile(path.join(destination, 'sprint-8-poses.png'))

  for (const [offset, name] of [[0, 'carrying'], [8, 'empty']]) {
    const animation = await Promise.all(strips.slice(offset, offset + 8).map(frame =>
      sharp(frame).flatten({background: '#3b444c'}).raw().toBuffer()))
    await sharp(Buffer.concat(animation), {
      raw: {width: frameSize, height: frameSize * 8, channels: 3, pageHeight: frameSize},
    }).gif({loop: 0, delay: [60, 60, 50, 60, 60, 50, 60, 60]}).toFile(path.join(destination, 'sprint-' + name + '.gif'))
  }
}

function validateContacts(facing, worldDirection, joints) {
  const length = Math.hypot(...worldDirection)
  const advance = [worldDirection[0] * 8 / length, worldDirection[1] * 8 / length * 0.6]
  for (const side of ['right', 'left']) {
    const contacts = joints.map(pose => pose[side]).filter(pose => pose.phase <= 2)
      .sort((a, b) => a.phase - b.phase)
    assert.deepEqual(contacts.map(pose => pose.phase), [0, 1, 2], facing + ' ' + side)
    for (let sample = 1; sample < contacts.length; sample++) {
      assert(contacts[sample].pitch === 0)
      const before = contacts[sample - 1].ankle
      const after = contacts[sample].ankle
      const error = after.map((value, axis) => value - before[axis] + advance[axis])
      assert(Math.hypot(...error) < 1e-9, facing + ' ' + side + ' foot slides')
    }
  }
}

async function bake(facing, check) {
  const slug = facing.replaceAll('_', '-')
  const results = []
  for (const empty of [false, true]) {
    const result = await renderSprintAtlas(facing, gait, empty)
    const {pixels, joints, facing: worldDirection} = result
    assert.equal(pixels.length, width * height * 4)
    validateContacts(facing, worldDirection, joints)
    const poses = await frames(pixels)
    assert.equal(new Set(poses.map(frame => frame.toString('base64'))).size, 8)
    results.push(result)
    if (empty && occludedParcel.has(facing)) {
      assert(pixels.equals(results[0].pixels), facing + ' parcel is visible')
      continue
    }
    const file = path.join(assets, 'r8d-sprint-' + slug + (empty ? '-empty' : '') + '.png')
    if (check) {
      assert(pixels.equals(await sharp(file).ensureAlpha().raw().toBuffer()), file)
    } else {
      await sharp(pixels, {raw}).png().toFile(file)
    }
  }
  if (!check) await writeReview(...results.map(result => result.pixels), path.join(review, slug))
  return {direction: results[0].facing, poses: results[0].joints}
}

async function main() {
  const check = process.argv.includes('--check')
  const joints = {}
  for (const facing of facings) joints[facing] = await bake(facing, check)
  if (!check) await fs.writeFile(path.join(review, 'sprint-joints.json'), JSON.stringify(joints, null, 2) + '\n')
  console.log('Eight poses and flat-contact distances verified for all eight sprint directions')
}

main().catch(error => {console.error(error); process.exitCode = 1})
