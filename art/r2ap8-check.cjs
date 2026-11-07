const assert = require('node:assert/strict')
const {execFileSync} = require('node:child_process')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const zombie = require('./zombie/r2za-zombie-attack.cjs')
const {facings} = require('./zombie/raster.cjs')
const {facings: zombieRigs} = require('./zombie/r2z-rig.json')
const zombieAttacks = require('./zombie/r2za-rigs.json')

const root = path.resolve(__dirname, '..')
const review = path.join(root, 'output/review/R2-AP8')
const baseline = '9d6e1d3'
const directions = facings.filter(facing => facing !== 'front_right')
const zombieFile = 'game/assets/zombie/r2za-zombie-attack-20261106'
const original = file => execFileSync('git', ['show', `${baseline}:${file}`], {cwd: root, maxBuffer: 8 * 1024 * 1024})
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

function layout(cells, size, columns) {
  const width = size * columns, height = size * Math.ceil(cells.length / columns)
  const pixels = Buffer.alloc(width * height * 4)
  for (const [i, sprite] of cells.entries()) {
    const left = i % columns * size, top = Math.floor(i / columns) * size
    for (let y = 0; y < size; y++) {
      sprite.copy(pixels, ((top + y) * width + left) * 4, y * size * 4, (y + 1) * size * 4)
    }
  }
  return sharp(pixels, {raw: {width, height, channels: 4}})
    .flatten({background: '#566972'}).resize(width * 2, height * 2, {kernel: 'nearest'})
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
    let previous = -2
    for (const [left, right] of spans) {
      assert(left > previous + 1 && left <= right && right < size)
      mask.fill(1, Number(y) * size + left, Number(y) * size + right + 1)
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

async function main() {
  const preview = process.argv.includes('--preview')
  if (preview) await fs.mkdir(review, {recursive: true})
  const zombies = await checkZombie(preview)
  if (!preview) assert(Object.values(zombies).every(result => !Object.keys(result.detached).length))
  console.log(JSON.stringify(zombies))
}
main().catch(error => {console.error(error); process.exitCode = 1})
