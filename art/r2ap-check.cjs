const assert = require('node:assert/strict')
const {execFileSync} = require('node:child_process')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {buildR2ap} = require('./player/r2a-combat-assets.cjs')
const {makeAtlas} = require('./zombie/r2za-zombie-attack.cjs')
const {weights} = require('./zombie/r2ap-front-right.json')
const {bodyDrop} = require('./player/consistent-rig.json')

const root = path.resolve(__dirname, '..')
const baseline = 'ed4d20a'
const combat = 'game/assets/combat'
const zombie = 'game/assets/zombie/r2za-zombie-attack-20261106'
const playerPngs = ['r2a-attack-front-right-20261106.png', 'r2aw-attack-walk-front-right-20261106.png']
const published = [...playerPngs.map(name => `${combat}/${name}`), zombie + '.png', zombie + '.json']
const git = (...args) => execFileSync('git', args, {cwd: root})
const original = file => git('show', `${baseline}:${file}`)
const read = file => fs.readFile(path.join(root, file))

function cell(pixels, width, [left, top, size]) {
  const result = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y++) {
    const from = ((top + y) * width + left) * 4
    pixels.copy(result, y * size * 4, from, from + size * 4)
  }
  return result
}

function verifySprite(sprite, size, frame) {
  const mask = new Uint8Array(size * size)
  if (frame?.opaque_rows) {
    for (const [y, spans] of Object.entries(frame.opaque_rows)) {
      for (const [left, right] of spans) mask.fill(1, y * size + left, y * size + right + 1)
    }
  }
  let area = 0
  for (let p = 0; p < mask.length; p++) {
    const alpha = sprite[p * 4 + 3]
    assert(alpha === 0 || alpha === 255)
    if (frame?.opaque_rows) assert.equal(mask[p] * 255, alpha)
    mask[p] = Number(Boolean(alpha))
    if (!alpha) continue
    const x = p % size, y = Math.floor(p / size)
    assert(x > 0 && x < size - 1 && y > 0 && y < size - 1)
    area++
  }
  assert(area > 0)
  const seed = mask.indexOf(1), queue = [seed]
  mask[seed] = 0
  const neighbors = [-size-1, -size, -size+1, -1, 1, size-1, size, size+1]
  for (let i = 0; i < queue.length; i++) {
    for (const offset of neighbors) {
      const p = queue[i] + offset
      if (!mask[p]) continue
      mask[p] = 0
      queue.push(p)
    }
  }
  assert.equal(queue.length, area, 'disconnected sprite pixels')
}

function forwardBat(frame, weapon, drop) {
  const size = 96
  let tipX = 0, otherX = 0
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const p = (y * size + x) * 4
    if (!frame[p + 3]) continue
    if (y >= drop && frame.readUInt32LE(p) === weapon.readUInt32LE(p - drop * size * 4)) {
      tipX = Math.max(tipX, x)
    } else {
      otherX = Math.max(otherX, x)
    }
  }
  assert(tipX > otherX, 'bat tip in front of body and package')
  return {tipX, otherX}
}

function handReach(result, index, side) {
  const [tx, ty] = result.poses[index][side].tip.map((value, axis) => value + weights[index][axis])
  const layer = result.layers[index][side], frame = result.frames[index]
  let xMax = 0, projected = 0
  for (let y = 0; y < 80; y++) for (let x = 0; x < 80; x++) {
    if (Math.hypot(x - tx, y - ty) > 5) continue
    const p = (y * 80 + x) * 4
    if (!layer[p + 3] || layer.readUInt32LE(p) !== frame.readUInt32LE(p)) continue
    xMax = Math.max(xMax, x)
    // Front-right screen projection for the fixed oblique view.
    projected = Math.max(projected, x + .6 * y)
  }
  assert(xMax > 0)
  return {xMax, projected}
}

async function checkPlayer() {
  const metaFile = `${combat}/r2a-combat-20261106.json`
  const meta = await read(metaFile)
  assert(meta.equals(original(metaFile)), 'unchanged player timing, clips, and pivots')
  const metadata = JSON.parse(meta)
  const result = await buildR2ap()
  assert.equal(metadata.attack.frames[4].start, .18)
  assert.equal(metadata.attack.frames.at(-1).end, .60)
  for (const [index, key] of ['attack', 'attack_walk'].entries()) {
    const file = `${combat}/${playerPngs[index]}`
    const [width, height] = metadata[key].canvas_size
    const current = await sharp(await read(file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    const old = await sharp(original(file)).ensureAlpha().raw().toBuffer()
    assert.deepEqual([current.info.width, current.info.height], [width, height])
    const cells = index ? result.walk.cells : result.cells
    const recovery = index ? 88 : 11
    assert.equal(cells.length, index ? 96 : 12)
    for (const [i, frame] of metadata[key].frames.entries()) {
      const pose = cell(current.data, width, frame.clip_topleft)
      verifySprite(pose, 96)
      assert(pose.equals(cells[i]), 'player PNG reproduces')
      if (i >= recovery) assert(pose.equals(cell(old, width, frame.clip_topleft)), 'original recovery')
    }
  }
  const [gx, gy] = result.hit.grip.map(n => Math.round(n) + 8)
  for (const layer of [result.hit.arm, result.hit.weapon]) {
    assert([-1, 0, 1].some(dy => [-1, 0, 1].some(dx => layer[((gy + dy) * 96 + gx + dx) * 4 + 3])))
  }
  const stationary = forwardBat(result.cells[4], result.hit.weapon, 0)
  const walking = bodyDrop.map((drop, phase) => forwardBat(result.walk.cells[32 + phase], result.hit.weapon, drop))
  return {stationary, walking}
}

async function checkZombie() {
  const metadata = JSON.parse(await read(zombie + '.json'))
  const before = JSON.parse(original(zombie + '.json'))
  const png = await read(zombie + '.png')
  const current = await sharp(png).ensureAlpha().raw().toBuffer({resolveWithObject: true})
  const old = await sharp(original(zombie + '.png')).ensureAlpha().raw().toBuffer()
  assert.deepEqual([current.info.width, current.info.height], [640, 960])
  const {pixels, metadata: rebuilt, results} = await makeAtlas()
  assert(current.data.equals(pixels))
  assert.deepEqual(metadata, rebuilt)
  assert.equal(metadata.facings.front_right[6].start, .30)
  assert.equal(metadata.facings.front_right.at(-1).end, .80)
  for (const [facing, frames] of Object.entries(metadata.facings)) {
    assert.equal(frames.length, 12)
    for (const [i, frame] of frames.entries()) {
      const previousFrame = before.facings[facing][i]
      const {opaque_rows: oldMask, ...oldPose} = previousFrame
      const {opaque_rows: newMask, ...pose} = frame
      assert.deepEqual(pose, oldPose)
      const previous = cell(old, 640, frame.clip_topleft)
      const currentCell = cell(current.data, 640, frame.clip_topleft)
      if (facing !== 'front_right' || i === 11) {
        assert(currentCell.equals(previous), 'other directions and final recovery pixels')
        assert.deepEqual(newMask, oldMask)
      } else {
        assert(currentCell.subarray(58 * 80 * 4).equals(previous.subarray(58 * 80 * 4)), 'fixed ground contact')
        verifySprite(currentCell, 80, frame)
      }
    }
  }
  const fr = results.find(result => result.facing === 'front_right')
  return Object.fromEntries(['right', 'left'].map(side => {
    const rows = weights.map((_, i) => handReach(fr, i, side))
    const hit = rows[6]
    assert(rows.every((row, i) => i === 6 || hit.xMax > row.xMax && hit.projected > row.projected))
    return [side, hit]
  }))
}

async function main() {
  const changed = git('diff', '--name-only', baseline, '--', 'game/assets').toString().trim().split(/\r?\n/)
  assert.deepEqual(changed.sort(), published.sort(), 'only approved product files')
  const frozen = await Promise.all(published.map(read))
  const [bat, hands] = await Promise.all([checkPlayer(), checkZombie()])
  for (const [i, file] of published.entries()) assert((await read(file)).equals(frozen[i]))
  console.log(JSON.stringify({baseline, player: 12, walking: 96, zombie: 12, bat, hands}))
}

main().catch(error => {console.error(error); process.exitCode = 1})
