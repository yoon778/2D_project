const assert = require('node:assert/strict')
const {execFileSync} = require('node:child_process')
const {createHash} = require('node:crypto')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const zombie = require('./zombie/r2za-zombie-attack.cjs')
const player = require('./player/r2c8-combat-assets.cjs')
const {buildR2ap} = require('./player/r2a-combat-assets.cjs')
const swingPoses = require('./player/r2ap-front-right.json')
const {renderWalkAtlas} = require('./player/consistent-walk.cjs')
const {bodyDrop} = require('./player/consistent-rig.json')
const {facings} = require('./zombie/raster.cjs')
const {facings: zombieRigs} = require('./zombie/r2z-rig.json')
const zombieAttacks = require('./zombie/r2za-rigs.json')

const root = path.resolve(__dirname, '..')
const review = path.join(root, 'output/review/R2-AP8')
const baseline = '9d6e1d3'
const recoveryBaseline = '0c7eb9a'
const swingBaseline = '29a659f'
const directions = facings.filter(facing => facing !== 'front_right')
const zombieFile = 'game/assets/zombie/r2za-zombie-attack-20261106'
const combat = 'game/assets/combat'
const swingImages = ['r2a-attack-front-right-20261106.png', 'r2aw-attack-walk-front-right-20261106.png']
const original = (file, ref = baseline) =>
  execFileSync('git', ['show', `${ref}:${file}`], {cwd: root, maxBuffer: 8 * 1024 * 1024})
const read = file => fs.readFile(path.join(root, file))
const raw = image => sharp(image).ensureAlpha().raw().toBuffer()

function cell(pixels, width, [left, top, size]) {
  const result = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y++) {
    const from = ((top + y) * width + left) * 4
    pixels.copy(result, y * size * 4, from, from + size * 4)
  }
  return result
}

const recoveryRows = {
  front_left: {3: 67, 4: 67, 5: 68},
  back_left: {0: 57, 1: 58, 6: 57, 7: 57},
}

function recoveryPixels(facing, phase) {
  const top = recoveryRows[facing]?.[phase]
  if (top === undefined) return []
  if (facing === 'back_left') return [0, 1, 2, 3].map(row => [47, top + row])
  return [[32, top], ...[1, 2, 3].flatMap(row => [[31, top + row], [32, top + row]])]
}

function clearPixels(image, width, coords, left, top) {
  for (const [x, y] of coords) {
    const p = ((top + y) * width + left + x) * 4
    assert.equal(image[p + 3], 255, 'approved pixel was opaque')
    image.fill(0, p, p + 4)
  }
}

async function checkRecoveryScope(preview) {
  const atlasFile = 'game/assets/player/r1b-courier-atlas-20261104.json'
  const expectedAtlas = JSON.parse(original(atlasFile, recoveryBaseline))
  const changed = [atlasFile, ...swingImages.map(image => `${combat}/${image}`)]
  for (const facing of Object.keys(recoveryRows)) {
    const slug = facing.replaceAll('_', '-')
    const walkFile = `game/assets/player/r1-consistent-${slug}-20261105.png`
    const attackFile = `${combat}/r2c8-attack-walk-${slug}-20261106.png`
    changed.push(walkFile, attackFile)
    const walk = await raw(original(walkFile, recoveryBaseline))
    const attack = await raw(original(attackFile, recoveryBaseline))
    for (let phase = 0; phase < 8; phase++) {
      const coords = recoveryPixels(facing, phase)
      if (!coords.length) continue
      const left = phase % 4 * 80, top = Math.floor(phase / 4) * 80
      const old = cell(walk, 320, [left, top, 80])
      const [fragment, ...others] = disconnected(old, 80)
      assert.equal(others.length, 0)
      assert.deepEqual(new Set(fragment.map(([x, y]) => y * 80 + x)),
        new Set(coords.map(([x, y]) => y * 80 + x)))
      clearPixels(walk, 320, coords, left, top)
      clearPixels(attack, 768, coords, phase * 96 + 8, 11 * 96 + 8)
      assert.equal(disconnected(cell(walk, 320, [left, top, 80]), 80).length, 0)
    }
    const png = await read(walkFile)
    expectedAtlas.sources[`consistent_${facing}`].sha256 = createHash('sha256').update(png).digest('hex')
    const actual = await sharp(png).ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height], [320, 240])
    assert(actual.data.equals(walk), `${facing} exact walk pixel scope`)
    assert((await renderWalkAtlas(facing)).equals(walk), `${facing} walk reproduction`)
    if (!preview) assert((await raw(await read(attackFile))).equals(attack), `${facing} exact recovery pixel scope`)
  }
  assert.deepEqual(JSON.parse(await read(atlasFile)), expectedAtlas, 'only the two walk PNG hashes may change')
  if (!preview) {
    const files = execFileSync('git', ['diff', '--name-only', recoveryBaseline, '--', 'game/assets'], {cwd: root})
      .toString().trim().split(/\r?\n/)
    assert.deepEqual(files.sort(), changed.sort(), 'only approved recovery and swing assets changed')
  }
}

function layout(cells, size, columns, scale = 2) {
  const width = size * columns, height = size * Math.ceil(cells.length / columns)
  const pixels = Buffer.alloc(width * height * 4)
  for (const [i, sprite] of cells.entries()) {
    const left = i % columns * size, top = Math.floor(i / columns) * size
    for (let y = 0; y < size; y++) {
      sprite.copy(pixels, ((top + y) * width + left) * 4, y * size * 4, (y + 1) * size * 4)
    }
  }
  return sharp(pixels, {raw: {width, height, channels: 4}})
    .flatten({background: '#566972'}).resize(width * scale, height * scale, {kernel: 'nearest'})
}

function disconnected(sprite, size) {
  const remaining = new Set()
  for (let p = 0; p < size * size; p++) {
    if (sprite[p * 4 + 3]) remaining.add(p)
  }
  const components = []
  while (remaining.size) {
    const queue = [remaining.values().next().value]
    remaining.delete(queue[0])
    for (let i = 0; i < queue.length; i++) {
      const x = queue[i] % size, y = Math.floor(queue[i] / size)
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const xx = x + dx, yy = y + dy
        if (xx < 0 || xx >= size || yy < 0 || yy >= size) continue
        const next = yy * size + xx
        if (remaining.delete(next)) queue.push(next)
      }
    }
    components.push(queue)
  }
  return components.sort((a, b) => b.length - a.length).slice(1)
    .map(group => group.map(p => [p % size, Math.floor(p / size)]))
}

function checkMask(sprite, size, rows, tag) {
  const mask = new Uint8Array(size * size)
  for (const [y, spans] of Object.entries(rows || {})) {
    const row = Number(y)
    assert(Number.isInteger(row) && row >= 0 && row < size)
    let previous = -2
    for (const [left, right] of spans) {
      assert(Number.isInteger(left) && Number.isInteger(right))
      assert(left > previous + 1 && left <= right && right < size)
      mask.fill(1, row * size + left, row * size + right + 1)
      previous = right
    }
  }
  for (let p = 0; p < size * size; p++) {
    const alpha = sprite[p * 4 + 3]
    assert(alpha === 0 || alpha === 255, tag)
    if (rows) assert.equal(mask[p] * 255, alpha, tag)
    if (!alpha) continue
    const x = p % size, y = Math.floor(p / size)
    assert(x > 0 && y > 0 && x < size - 1 && y < size - 1, `${tag} cell edge`)
  }
}

function zombieReach(result, rig, side, index) {
  const weight = result.weights?.[index] || [0, 0]
  const [tx, ty] = result.poses[index][side].tip.map((value, axis) => value + weight[axis])
  const layer = result.layers[index][side], frame = result.frames[index]
  const [fx, fy] = rig.worldFacing
  let reach = null
  for (let y = 0; y < 80; y++) for (let x = 0; x < 80; x++) {
    if (Math.hypot(x - tx, y - ty) > 5) continue
    const p = (y * 80 + x) * 4
    if (!layer[p + 3] || layer.readUInt32LE(p) !== frame.readUInt32LE(p)) continue
    const projection = fx * x + fy * .6 * y
    reach = Math.max(reach ?? -Infinity, projection)
  }
  return reach
}

function batReach(frame, layer, rig, drop) {
  const [fx, fy] = rig.worldFacing
  const [gx, gy] = layer.grip.map((value, axis) => value + 8 + (axis ? drop : 0))
  const [dx, dy] = layer.end.map((value, axis) => value - layer.grip[axis])
  const length = Math.hypot(dx, dy)
  let ahead = 0, visibleTipPixels = 0
  for (let y = drop; y < 96; y++) for (let x = 0; x < 96; x++) {
    const p = (y * 96 + x) * 4, q = ((y - drop) * 96 + x) * 4
    if (!layer.weapon[q + 3] || layer.weapon.readUInt32LE(q) !== frame.readUInt32LE(p)) continue
    const along = ((x - gx) * dx + (y - gy) * dy) / length
    if (along > length * .7) visibleTipPixels++
    ahead = Math.max(ahead, fx * (x - gx) + fy * .6 * (y - gy))
  }
  return {ahead: Math.round(ahead * 10) / 10, visibleTipPixels}
}

function gripConnected({arm, weapon, grip}) {
  const [gx, gy] = grip.map(value => Math.round(value) + 8)
  for (let y = gy - 3; y <= gy + 3; y++) for (let x = gx - 3; x <= gx + 3; x++) {
    if (!arm[(y * 96 + x) * 4 + 3]) continue
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (weapon[((y + dy) * 96 + x + dx) * 4 + 3]) return true
    }
  }
  return false
}

function checkGear(sprite, gear, drop, tag) {
  const offset = drop * 96 * 4
  for (let p = 0; p < gear.length - offset; p += 4) {
    if (gear[p + 3]) assert.equal(sprite.readUInt32LE(p + offset), gear.readUInt32LE(p), tag)
  }
}

async function makePreview(tag, old, next, size, times) {
  const key = [0, 2, times.indexOf(times.at(-1) === .8 ? .30 : .18), 7, 10, 11]
  const sheets = [...key.map(i => old[i]), ...key.map(i => next[i])]
  await layout(sheets, size, key.length).png().toFile(path.join(review, tag + '.png'))
  const pages = [await layout([old.at(-1), next.at(-1)], size, 2).raw().toBuffer()]
  for (const [i, frame] of next.entries()) {
    pages.push(await layout([old[i], frame], size, 2).raw().toBuffer())
  }
  const pageHeight = size * 2, width = size * 4
  const raw = {width, height: pageHeight * pages.length, channels: 3, pageHeight}
  const delays = [400, ...times.slice(1).map((t, i) => Math.round((t - times[i]) * 1000))]
  const gifTimes = times.map(t => Math.round(Math.round(t * 1000) / 10) * 10)
  const gifDelays = [400, ...gifTimes.slice(1).map((t, i) => t - gifTimes[i])]
  const animation = sharp(Buffer.concat(pages), {raw})
  await Promise.all([
    animation.clone().webp({delay: delays, loop: 0, lossless: true}).toFile(path.join(review, tag + '.webp')),
    animation.gif({delay: gifDelays, loop: 0, dither: 0}).toFile(path.join(review, tag + '.gif')),
  ])
}

async function checkZombie(preview) {
  const oldMeta = JSON.parse(original(zombieFile + '.json'))
  const old = await raw(original(zombieFile + '.png'))
  const result = await zombie.makeAtlas()
  const baselineLayout = structuredClone(result.metadata)
  for (const facing of directions) {
    for (const [i, frame] of baselineLayout.facings[facing].entries()) {
      if (i !== 11) frame.opaque_rows = oldMeta.facings[facing][i].opaque_rows
    }
  }
  assert.deepEqual(baselineLayout, oldMeta)
  if (!preview) {
    assert(result.pixels.equals(await raw(await read(zombieFile + '.png'))), 'zombie RGBA reproducible')
    assert.deepEqual(result.metadata, JSON.parse(await read(zombieFile + '.json')))
  }
  const report = {}, overview = []
  for (const item of result.results) {
    const {facing, frames} = item, rig = zombieRigs[facing]
    const clips = oldMeta.facings[facing].map(frame => frame.clip_topleft)
    const before = clips.map(clip => cell(old, 640, clip))
    if (facing === 'front_right') {
      assert(frames.every((frame, i) => frame.equals(before[i])))
      continue
    }
    assert(frames[11].equals(before[11]))
    const detached = {}
    for (const [i, frame] of frames.entries()) {
      const boot = zombieAttacks[facing].protectFromY * 80 * 4
      assert(frame.subarray(boot).equals(before[i].subarray(boot)), `${facing} boots ${i}`)
      checkMask(frame, 80, result.metadata.facings[facing][i].opaque_rows, `${facing} ${i}`)
      const groups = disconnected(frame, 80)
      if (groups.length) detached[i] = groups
    }
    const handReach = Object.fromEntries(['left', 'right'].map(side =>
      [side, zombie.times.slice(0, 11).map((_, i) => zombieReach(item, rig, side, i))]))
    for (const [side, reaches] of Object.entries(handReach)) {
      assert(reaches[6] !== null && reaches.every((reach, i) => i === 6 || reach === null || reach < reaches[6]),
        `${facing} ${side} visible hand reach peaks at the hit`)
    }
    report[facing] = {detached, handReach}
    if (preview) {
      overview.push(...[2, 6, 9].map(i => before[i]), ...[2, 6, 9].map(i => frames[i]))
      await makePreview(`zombie-${facing.replaceAll('_', '-')}`, before, frames, 80, zombie.times)
    }
  }
  if (preview) {
    await layout(overview, 80, 6).png().toFile(path.join(review, 'zombie-seven-directions.png'))
    await fs.writeFile(path.join(review, 'zombie-check.json'), JSON.stringify(report, null, 2) + '\n')
  }
  const r2zt = 'game/assets/zombie/r2z-zombie-20261106'
  assert((await read(r2zt + '.png')).equals(original(r2zt + '.png')), 'R2-ZT walking and recoil')
  assert.deepEqual(JSON.parse(await read(r2zt + '.json')), JSON.parse(original(r2zt + '.json')))
  return report
}

function swingTip(pose) {
  const hand = pose.hand * Math.PI / 180
  const bat = pose.bat * Math.PI / 180
  // Representative distal axis point, relative to the native grip at (29, 52).
  return [
    pose.wrist[0] + Math.cos(hand) - 6 * Math.sin(hand) - 2 * Math.cos(bat) - 20 * Math.sin(bat),
    pose.wrist[1] + Math.sin(hand) + 6 * Math.cos(hand) - 2 * Math.sin(bat) + 20 * Math.cos(bat),
  ]
}

async function checkFrontRightSwing(metadata, preview) {
  const result = await buildR2ap()
  assert.deepEqual(result.times, [...metadata.attack.frames.map(frame => frame.start), .60])
  assert.deepEqual(result.walk.frames, metadata.attack_walk.frames)
  const tips = swingPoses.map(swingTip)
  for (let i = 1; i < tips.length; i++) {
    assert(Math.hypot(...tips[i].map((value, axis) => value - tips[i - 1][axis])) <= 40)
  }
  assert(gripConnected(result.hit), 'front-right hit grip contact')
  const hit = {...result.hit, end: tips[4]}
  assert(hit.end.every((value, axis) => value > hit.grip[axis]), 'hit crosses diagonally down and forward')
  const [dx, dy] = swingPoses[3].weight
  const idle = result.cells.at(-1)
  for (const [drop, phase] of [[0, -1], ...bodyDrop.map((drop, phase) => [drop, phase])]) {
    const preHit = phase < 0 ? result.cells[3] : result.walk.cells[24 + phase]
    for (let y = 8; y <= 38; y++) for (let x = 38; x < 96; x++) {
      const p = (y * 96 + x) * 4
      if (!idle[p + 3]) continue
      const q = ((y + dy + drop) * 96 + x + dx) * 4
      assert.equal(preHit.readUInt32LE(q), idle.readUInt32LE(p), 'pre-hit face remains visible')
    }
    const frame = phase < 0 ? result.cells[4] : result.walk.cells[32 + phase]
    const reach = batReach(frame, hit, zombieRigs.front_right, drop)
    assert(reach.ahead > 0 && reach.visibleTipPixels > 0)
  }
  for (const [index, key] of ['attack', 'attack_walk'].entries()) {
    const spec = metadata[key], count = index ? 8 : 1
    assert.equal(spec.image, swingImages[index])
    const [width, height] = spec.canvas_size
    const file = `${combat}/${spec.image}`
    const before = await raw(original(file, swingBaseline))
    const cells = index ? result.walk.cells : result.cells
    assert.equal(cells.length, 12 * count)
    let actual
    if (!preview) {
      const image = await sharp(await read(file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
      assert.deepEqual([image.info.width, image.info.height], [width, height])
      actual = image.data
    }
    for (const [i, frame] of spec.frames.entries()) {
      const pose = cells[i], attack = Math.floor(i / count)
      const tag = `front_right ${key} ${i}`
      checkMask(pose, 96, null, tag)
      assert.equal(disconnected(pose, 96).length, 0, tag)
      assert.equal(pose.equals(cell(before, width, frame.clip_topleft)), attack === 0 || attack > 5, tag)
      if (actual) assert(pose.equals(cell(actual, width, frame.clip_topleft)), tag)
    }
  }
}

async function checkPlayer(preview) {
  const file = `${combat}/r2a-combat-20261106.json`
  const metadata = JSON.parse(await read(file))
  assert.deepEqual(metadata, JSON.parse(original(file)))
  await checkFrontRightSwing(metadata, preview)
  const report = {}, overview = []
  for (const facing of directions) {
    const item = await player.build(facing), rig = zombieRigs[facing]
    const slug = facing.replaceAll('_', '-')
    const {stationary, moving, layers} = item
    const detached = {}, recoveryFragments = {}, gripGaps = [], reaches = []
    for (const [key, frames, count] of [['attack', stationary, 1], ['attack_walk', moving, 8]]) {
      const spec = metadata[`${key}_${facing}`]
      assert.deepEqual(item[key], spec)
      const [width, height] = spec.canvas_size
      const file = `${combat}/${spec.image}`
      const baselinePixels = await raw(original(file))
      const before = spec.frames.map(frame => cell(baselinePixels, width, frame.clip_topleft))
      let actual
      if (!preview) {
        const image = await sharp(await read(file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
        assert.deepEqual([image.info.width, image.info.height], [width, height])
        actual = image.data
      }
      for (const [i, sprite] of frames.entries()) {
        const tag = `${facing} ${key} ${i}`
        checkMask(sprite, 96, null, tag)
        if (actual) assert(sprite.equals(cell(actual, width, spec.frames[i].clip_topleft)), tag)
        const recovery = i >= 11 * count
        if (recovery) {
          const expected = Buffer.from(before[i])
          if (count === 8) clearPixels(expected, 96, recoveryPixels(facing, i % 8), 8, 8)
          assert(sprite.equals(expected), `${tag} recovery after approved cleanup`)
        } else {
          checkGear(sprite, layers[Math.floor(i / count)].gear, count === 8 ? bodyDrop[i % 8] : 0, tag)
        }
        const groups = disconnected(sprite, 96)
        if (!groups.length) continue
        if (recovery) recoveryFragments[`${key}:${i}`] = groups
        else detached[`${key}:${i}`] = {groups, before: disconnected(before[i], 96)}
      }
      for (let phase = 0; phase < count; phase++) {
        reaches.push(batReach(frames[4 * count + phase], layers[4], rig, count === 8 ? bodyDrop[phase] : 0))
      }
      if (preview) {
        const walkAt = player.times.slice(0, 12).map((time, i) =>
          i * 8 + Math.floor((time + player.times[i + 1]) / 2 * 60 / 64 * 8) % 8)
        const indices = count === 8 ? walkAt : player.times.slice(0, 12).map((_, i) => i)
        const tag = `player-${count === 8 ? 'walking-' : ''}${slug}`
        await makePreview(tag, indices.map(i => before[i]), indices.map(i => frames[i]), 96, player.times)
        if (count === 1) {
          overview.push(...[2, 4, 9].map(i => before[i]), ...[2, 4, 9].map(i => frames[i]))
          if (facing === 'front_left') {
            await layout([before[4], frames[4]], 96, 2, 4).png()
              .toFile(path.join(review, 'player-front-left-hit-grip-4x.png'))
          }
        }
      }
    }
    for (const [i, layer] of layers.entries()) {
      checkMask(layer.weapon, 96, null, `${facing} weapon ${i}`)
      checkMask(layer.arm, 96, null, `${facing} arm ${i}`)
      if (!gripConnected(layer)) gripGaps.push(i)
    }
    report[facing] = {detached, recoveryFragments, gripGaps, reaches}
  }
  if (preview) {
    await layout(overview, 96, 6).png().toFile(path.join(review, 'player-seven-directions.png'))
    await fs.writeFile(path.join(review, 'player-check.json'), JSON.stringify(report, null, 2) + '\n')
  }
  return report
}

async function main() {
  const preview = process.argv.includes('--preview')
  if (preview) await fs.mkdir(review, {recursive: true})
  if (!process.argv.includes('--player')) {
    const zombies = await checkZombie(preview)
    if (!preview) assert(Object.values(zombies).every(result => !Object.keys(result.detached).length))
    console.log(JSON.stringify(zombies))
  }
  if (!process.argv.includes('--zombie')) {
    await checkRecoveryScope(preview)
    const players = await checkPlayer(preview)
    if (!preview) assert(Object.values(players).every(result => !Object.keys(result.detached).length &&
      !result.gripGaps.length && result.reaches.every(reach => reach.ahead > 0 && reach.visibleTipPixels > 0)))
    console.log(JSON.stringify(players))
  }
}
main().catch(error => {console.error(error); process.exitCode = 1})
