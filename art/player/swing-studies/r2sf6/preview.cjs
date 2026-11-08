// Generate the R2-SF6 comparison GIF and verify its encoded timeline.
const assert = require('node:assert/strict')
const {createHash} = require('node:crypto')
const fs = require('node:fs/promises')
const {createRequire} = require('node:module')
const os = require('node:os')
const path = require('node:path')
const {parseArgs} = require('node:util')

const ROOT = path.resolve(__dirname, '../../../..')
const CELL = 96
const POSES = 6
const PIVOT = [48, 80]
const SCALE = 3
const HIT_POSE = 3
const MARK_MS = 40
const SWING_MS = 660
const SHARED_IDLE_MS = 450
const WIDTH = 736
const HEIGHT = 384
const PANEL_WIDTH = 344
const GROUND_Y = 316
const SIDES = [
  {label: 'A 0.18s', left: 16, holds: [30, 90, 60, 60, 140, 220]},
  {label: 'B 0.24s', left: 376, holds: [30, 150, 60, 60, 140, 220]},
]

function loadSharp() {
  try {
    return require('sharp')
  } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error
    const runtime = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node')
    return createRequire(path.join(runtime, 'package.json'))('sharp')
  }
}

function cumulative(delays) {
  const edges = [0]
  for (const delay of delays) edges.push(edges.at(-1) + delay)
  return edges
}

function timeline() {
  const edges = SIDES.map(side => cumulative(side.holds))
  const hits = edges.map(side => side[HIT_POSE])
  assert.deepEqual(hits, [180, 240])
  assert.equal(Math.max(...edges.map(side => side.at(-1))), SWING_MS)
  assert.deepEqual(SIDES[0].holds.slice(HIT_POSE), SIDES[1].holds.slice(HIT_POSE))
  const cuts = [...new Set([...edges.flat(), ...hits.map(hit => hit + MARK_MS), SWING_MS + SHARED_IDLE_MS])]
    .sort((a, b) => a - b)
  return cuts.slice(0, -1).map((start, i) => {
    const delay = cuts[i + 1] - start
    assert(delay > 0 && delay % 10 === 0, 'GIF delays must be positive multiples of 10ms')
    return {
      start, delay,
      poses: edges.map(side => {
        const end = side.findIndex(edge => edge > start)
        return end < 0 ? 0 : end - 1
      }),
      marks: hits.map(hit => start >= hit && start < hit + MARK_MS),
    }
  })
}

async function readPoses(sharp, png) {
  const meta = await sharp(png).metadata()
  assert(meta.format === 'png' && meta.width === CELL * POSES && meta.height === CELL
    && (meta.pages ?? 1) === 1, 'Expected one 576×96 PNG containing six horizontal 96×96 cells')
  assert(meta.hasAlpha, 'Expected a PNG with transparency')
  const sprites = []
  const cells = []
  for (let i = 0; i < POSES; i++) {
    const {data, info} = await sharp(png).extract({left: i * CELL, top: 0, width: CELL, height: CELL})
      .toColourspace('srgb').ensureAlpha().raw().toBuffer({resolveWithObject: true})
    assert.equal(info.channels, 4)
    let transparent = 0
    for (let alpha = 3; alpha < data.length; alpha += 4) if (data[alpha] === 0) transparent++
    assert(transparent > 0 && transparent < CELL * CELL, 'Cell ' + i + ' needs visible pixels and transparent background')
    cells.push({index: i, transparentPixels: transparent, rgbaSha256: createHash('sha256').update(data).digest('hex')})
    sprites.push(await sharp(data, {raw: {width: CELL, height: CELL, channels: 4}})
      .resize(CELL * SCALE, CELL * SCALE, {kernel: 'nearest'}).png().toBuffer())
  }
  return {sprites, cells}
}

function markerX(side) {
  return side.left + PANEL_WIDTH - 88
}

function backdrop(marks) {
  const panels = SIDES.map((side, i) => {
    const {left, label} = side
    const marker = markerX(side)
    const hit = marks[i] ? [
      '<rect x="' + marker + '" y="35" width="66" height="26" rx="5" fill="#f8be65"/>',
      '<text x="' + (marker + 33) + '" y="53" text-anchor="middle" fill="#23201a" font-size="13">HIT</text>',
    ].join('') : ''
    return [
      '<rect x="' + left + '" y="16" width="' + PANEL_WIDTH + '" height="352" rx="12" fill="#27343d" stroke="#455966"/>',
      '<text x="' + (left + 22) + '" y="57" fill="#f0f4f5" font-size="23">' + label + '</text>',
      '<path d="M' + (left + 24) + ' ' + GROUND_Y + 'h296" stroke="#4b616e" stroke-dasharray="4 5"/>',
      hit,
    ].join('')
  }).join('')
  return Buffer.from('<svg width="' + WIDTH + '" height="' + HEIGHT + '" xmlns="http://www.w3.org/2000/svg">' +
    '<rect width="100%" height="100%" fill="#141d24"/>' +
    '<g font-family="Segoe UI,Arial,sans-serif" font-weight="700">' + panels + '</g></svg>')
}

async function makeGif(sharp, sprites, frames) {
  const pages = []
  for (const frame of frames) {
    const layers = SIDES.map((side, i) => ({
      input: sprites[frame.poses[i]],
      left: side.left + PANEL_WIDTH / 2 - PIVOT[0] * SCALE,
      top: GROUND_Y - PIVOT[1] * SCALE,
    }))
    pages.push(await sharp(backdrop(frame.marks)).composite(layers).removeAlpha().raw().toBuffer())
  }
  return sharp(Buffer.concat(pages), {
    raw: {width: WIDTH, height: HEIGHT * pages.length, pageHeight: HEIGHT, channels: 3},
  }).gif({delay: frames.map(frame => frame.delay), loop: 0, dither: 0, keepDuplicateFrames: true}).toBuffer()
}

async function verifyGif(sharp, gif, frames) {
  const decoder = sharp(gif, {animated: true})
  const meta = await decoder.metadata()
  assert.equal(meta.format, 'gif')
  assert.deepEqual([meta.width, meta.pageHeight, meta.pages, meta.loop], [WIDTH, HEIGHT, frames.length, 0])
  assert.deepEqual(meta.delay, frames.map(frame => frame.delay), 'Encoded GIF frame delays changed')
  const starts = cumulative(meta.delay)
  const {data, info} = await decoder.removeAlpha().raw().toBuffer({resolveWithObject: true})
  assert.equal(info.channels, 3)
  const hits = SIDES.map((side, i) => {
    const x = markerX(side) + 12
    const y = 48
    const active = frames.map((frame, page) => {
      const offset = ((page * HEIGHT + y) * WIDTH + x) * info.channels
      const [r, g, b] = data.subarray(offset, offset + 3)
      const marked = r > 190 && g > 130 && b < 160
      assert.equal(marked, frame.marks[i], 'Encoded hit marker differs at frame ' + page)
      return marked
    })
    const hitPage = frames.findIndex(frame => frame.poses[i] === HIT_POSE)
    assert.equal(hitPage, active.indexOf(true))
    const hitMs = starts[hitPage]
    const markerMs = active.reduce((total, on, page) => total + (on ? meta.delay[page] : 0), 0)
    assert.equal(markerMs, MARK_MS)
    const end = cumulative(side.holds).at(-1)
    const holdsMs = Array(POSES).fill(0)
    for (const [page, frame] of frames.entries()) {
      if (starts[page] < end) holdsMs[frame.poses[i]] += meta.delay[page]
    }
    assert.deepEqual(holdsMs, side.holds)
    return {label: side.label, holdsMs, hitMs, markerMs, idlePaddingMs: SWING_MS - end}
  })
  assert.deepEqual(hits.map(side => side.hitMs), [180, 240])
  assert.deepEqual(hits[0].holdsMs.slice(HIT_POSE), hits[1].holdsMs.slice(HIT_POSE))
  assert.equal(starts.at(-2), SWING_MS)
  assert.equal(meta.delay.at(-1), SHARED_IDLE_MS)
  assert.deepEqual(frames.at(-1).poses, [0, 0])
  return {swingMs: SWING_MS, sharedIdleMs: SHARED_IDLE_MS, loopMs: starts.at(-1), delaysMs: meta.delay, sides: hits}
}

async function main() {
  const {values} = parseArgs({options: {input: {type: 'string'}, output: {type: 'string'}}})
  const input = path.resolve(values.input ?? path.join(__dirname, 'poses.png'))
  const output = path.resolve(values.output ?? path.join(ROOT, 'output/review/R2-SF6'))
  const png = await fs.readFile(input)
  const sharp = loadSharp()
  const {sprites, cells} = await readPoses(sharp, png)
  const frames = timeline()
  const gif = await makeGif(sharp, sprites, frames)
  const verified = await verifyGif(sharp, gif, frames)
  const report = {
    input: path.relative(ROOT, input),
    inputSha256: createHash('sha256').update(png).digest('hex'),
    sheetPx: [CELL * POSES, CELL],
    cellPx: [CELL, CELL],
    footPivotPx: PIVOT,
    cells,
    frameSchedule: frames,
    ...verified,
  }
  await fs.mkdir(output, {recursive: true})
  await fs.writeFile(path.join(output, 'timing-comparison.gif'), gif)
  await fs.writeFile(path.join(output, 'timing.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify(verified))
  console.log(output)
}

main().catch(error => {
  console.error(error.message)
  process.exitCode = 1
})
