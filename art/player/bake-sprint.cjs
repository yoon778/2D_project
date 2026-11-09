// Offline bake of the front-right sprint using the approved courier parts.
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

// Three flat-foot contacts, then toe-off and a higher swing. The other leg
// follows four samples later. 8 native px × 1.5 display scale = 12 world px.
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

async function writeReview(held, empty) {
  const rows = [...await frames(held), ...await frames(empty)]
  const frameSize = cell * 3
  const strips = await Promise.all(rows.map(frame =>
    sharp(frame, {raw: {width: cell, height: cell, channels: 4}})
      .resize(frameSize, frameSize, {kernel: 'nearest'}).png().toBuffer()))
  await fs.mkdir(review, {recursive: true})
  await sharp({create: {width: frameSize * 8, height: frameSize * 2, channels: 4, background: '#3b444c'}})
    .composite(strips.map((input, index) => ({
      input, left: index % 8 * frameSize, top: Math.floor(index / 8) * frameSize,
    }))).png().toFile(path.join(review, 'sprint-8-poses.png'))

  for (const [offset, name] of [[0, 'carrying'], [8, 'empty']]) {
    const animation = await Promise.all(strips.slice(offset, offset + 8).map(frame =>
      sharp(frame).flatten({background: '#3b444c'}).raw().toBuffer()))
    await sharp(Buffer.concat(animation), {
      raw: {width: frameSize, height: frameSize * 8, channels: 3, pageHeight: frameSize},
    }).gif({loop: 0, delay: [60, 60, 50, 60, 60, 50, 60, 60]}).toFile(path.join(review, 'sprint-' + name + '.gif'))
  }
}

async function main() {
  const check = process.argv.includes('--check')
  const atlases = []
  for (const empty of [false, true]) {
    const pixels = await renderSprintAtlas(gait, empty)
    assert.equal(pixels.length, width * height * 4)
    const poses = await frames(pixels)
    assert.equal(new Set(poses.map(frame => frame.toString('base64'))).size, 8)
    const file = path.join(assets, 'r8d-sprint-front-right' + (empty ? '-empty' : '') + '.png')
    if (check) {
      assert(pixels.equals(await sharp(file).ensureAlpha().raw().toBuffer()), file)
    } else {
      await sharp(pixels, {raw}).png().toFile(file)
    }
    atlases.push(pixels)
  }
  if (!check) await writeReview(...atlases)
  console.log('8 front-right sprint poses per variant verified')
}

main().catch(error => {console.error(error); process.exitCode = 1})
