// Reuse the directional rig and author a broad-bodied zombie with an overhead windup.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const raster = require('./raster.cjs')
const {build, solve} = require('./r2za-zombie-attack.cjs')
const attackRigs = require('./r2za-rigs.json')
const bodyRig = require('./r2z-rig.json')
const {loadStates} = require('./r2z-zombie-assets.cjs')
const {shiftWeight} = require('../attack-weight.cjs')

const root = path.resolve(__dirname, '../..')
const assets = path.join(root, 'game/assets/zombie')
const review = path.join(root, 'output/review/heavy-zombie')
const {facings, size} = raster
const rowBytes = size * 4
const cellBytes = size * rowBytes
const times = [0, .08, .17, .26, .36, .51, .60, .69, .77, .87, .98, 1.08, 1.15]
const widths = [[20, 1], [27, 1.34], [33, 1.43], [46, 1.58], [52, 1.47], [62, 1.17], [67, 1]]
const fabric = new Map(Object.entries({
  '757660': '71868c', '70735d': '65787e', '6b6e59': '596b73', '58594a': '405059',
  '645e4f': '52616a', '504c42': '344048', '312f3a': '423b41', '353139': '51454b',
  '2b282b': '322c31', '4e4038': '383834', '644a3d': '645043', '60463a': '524039',
}).map(([from, to]) => [from, Buffer.from(to, 'hex')]))

function torsoWidth(y) {
  if (y < widths[0][0] || y >= widths.at(-1)[0]) return 1
  const index = widths.findIndex(([end]) => end > y)
  const [start, a] = widths[index - 1], [end, b] = widths[index]
  return a + (b - a) * (y - start) / (end - start)
}

function buildHeavyCell(frame, {dead = false} = {}) {
  const result = Buffer.alloc(cellBytes)
  raster.paint(result, frame, (x, y) => {
    if (dead) {
      // Broaden the fallen torso across the ground, around the horizontal body.
      const center = 58
      return [x, x >= 38 && x <= 58 ? center + (y - center) / 1.22 : y]
    }
    const delta = Math.abs(x - 40), widenedMiddle = 20 * torsoWidth(y)
    const sourceDelta = delta <= widenedMiddle ? delta * 20 / widenedMiddle
      : 20 + (delta - widenedMiddle) * 20 / (40 - widenedMiddle)
    return [40 + Math.sign(x - 40) * sourceDelta, y]
  })
  for (let offset = 0; offset < cellBytes; offset += 4) {
    if (!result[offset + 3]) continue
    const replace = fabric.get(result.subarray(offset, offset + 3).toString('hex'))
    if (replace) result.set(replace, offset)
  }
  return result
}

function overheadAim(model, near, side, facing, phase) {
  const [x, y] = model.shoulder
  const [startX, startY] = model.tip
  const horizontal = bodyRig.facings[facing].worldFacing[0]
  const outward = x >= 40 ? 1 : -1
  const raisedX = x + 4 * outward + horizontal * (side === near ? 1 : 3)
  const raisedY = y - 22 + (side === near ? 0 : 2)
  const lift = [0, .25, .56, .82, 1, .83][phase]
  const flaring = Math.sin(Math.PI * lift) * outward * 8
  const idleAngle = Math.atan2(startY - model.wrist[1], startX - model.wrist[0]) * 180 / Math.PI
  const angle = idleAngle + Math.atan2(Math.sin((-88 - idleAngle) * Math.PI / 180),
    Math.cos((-88 - idleAngle) * Math.PI / 180)) * 180 / Math.PI * lift
  return solve(model, [startX + (raisedX - startX) * lift + flaring, startY + (raisedY - startY) * lift], angle)
}

function extendRearShoulder(arm, [x, y]) {
  // The detached source mask on the back view has no fabric under the raised sleeve.
  // Continue the jacket into the shoulder socket, behind the torso layer.
  const inward = x < 40 ? 1 : -1
  for (let step = 0; step <= 6; step++) {
    const col = x + step * inward
    const center = y + Math.floor(step / 2)
    for (let row = center - 1; row <= center + 2; row++) {
      const pixel = (row * size + col) * 4
      if (!arm[pixel + 3]) arm.set([88, 89, 74, 255], pixel)
    }
  }
}

function removePoseSpecks(frame, facing, phase) {
  const visited = new Set()
  let connectedParts = 0
  for (let origin = 0; origin < size * size; origin++) {
    if (!frame[origin * 4 + 3] || visited.has(origin)) continue
    const part = [origin]
    visited.add(origin)
    for (let i = 0; i < part.length; i++) {
      const x = part[i] % size, y = Math.floor(part[i] / size)
      for (let row = Math.max(0, y - 1); row <= Math.min(size - 1, y + 1); row++) {
        for (let col = Math.max(0, x - 1); col <= Math.min(size - 1, x + 1); col++) {
          const pixel = row * size + col
          if (!visited.has(pixel) && frame[pixel * 4 + 3]) {
            visited.add(pixel)
            part.push(pixel)
          }
        }
      }
    }
    if (part.length > 6) connectedParts++
    else for (const pixel of part) frame.fill(0, pixel * 4, pixel * 4 + 4)
  }
  assert.equal(connectedParts, 1, `${facing} phase ${phase}: separated sprite limb`)
  return frame
}

function overheadFrame(facing, result, phase) {
  const config = attackRigs[facing]
  const near = config.nearArm, far = near === 'left' ? 'right' : 'left'
  const bodyLift = [0, 0, -1, -1, -2, 0][phase]
  const offset = [0, bodyLift]
  const shift = ([x, y]) => [x, y + bodyLift]
  const torso = shiftWeight(result.base, size, 0, offset, 43, config.protectFromY)
  const arms = {}
  for (const [side, model] of Object.entries(config.arms)) {
    const source = config.arms[model.textureFrom || side]
    const parts = result.parts[side]
    const pose = overheadAim(model, near, side, facing, phase)
    const arm = Buffer.alloc(cellBytes)
    raster.segment(arm, parts.upper, source.shoulder, source.elbow, shift(model.shoulder), shift(pose.elbow))
    raster.segment(arm, parts.fore, source.elbow, source.wrist, shift(pose.elbow), shift(pose.wrist))
    raster.rotate(arm, parts.hand, source.wrist, shift(pose.wrist), pose.handAngle)
    if (config.bothBehind) extendRearShoulder(arm, shift(model.shoulder))
    raster.outline(arm, bodyRig.outline)
    arms[side] = arm
  }
  const frame = Buffer.alloc(cellBytes)
  if (!config.bothFront) raster.overlay(frame, arms[far])
  if (config.bothBehind) raster.overlay(frame, arms[near])
  raster.overlay(frame, torso)
  if (config.bothFront) raster.overlay(frame, arms[far])
  if (!config.bothBehind) raster.overlay(frame, arms[near])
  result.source.copy(frame, config.protectFromY * rowBytes, config.protectFromY * rowBytes)
  return removePoseSpecks(buildHeavyCell(frame), facing, phase)
}

async function saveAtlas(pixels, metadata) {
  const [width, height] = metadata.canvas_size
  await raster.png(pixels, width, height, path.join(assets, metadata.image))
  await fs.writeFile(path.join(assets, metadata.image.replace(/\.png$/, '.json')), JSON.stringify(metadata) + '\n')
}

async function run() {
  const states = await loadStates({legacyWalk: true})
  const dead = buildHeavyCell(await readCell('r2z-zombie-20261106.png', 0, 13), {dead: true})
  for (const state of Object.values(states)) {
    state.idle = buildHeavyCell(state.idle)
    state.walk = state.walk.map(frame => buildHeavyCell(frame))
    state.hit = state.hit.map(frame => buildHeavyCell(frame))
    state.resume = state.resume.map(steps => steps.map(frame => buildHeavyCell(frame)))
  }
  const base = raster.atlas(states, dead)
  base.metadata.image = 'heavy-base.png'
  await saveAtlas(base.pixels, base.metadata)

  const width = facings.length * size, height = (times.length - 1) * size
  const pixels = Buffer.alloc(width * height * 4)
  const metadata = {image: 'heavy-attack.png', canvas_size: [width, height], cell_size: [size, size],
    scale: 2, reference_height: 64, facings: {}}
  for (const [col, facing] of facings.entries()) {
    const result = await build(facing)
    const frames = result.frames.map((frame, phase) => {
      if (phase === 0 || phase === 11) return states[facing].idle
      return phase <= 5 ? overheadFrame(facing, result, phase) : buildHeavyCell(frame)
    })
    const highest = frame => Math.min(...Object.keys(raster.opaqueRows(frame)).map(Number))
    assert(highest(frames[4]) < highest(frames[0]), `${facing}: overhead silhouette must rise`)
    metadata.facings[facing] = frames.map((frame, row) => {
      for (let y = 0; y < size; y++) frame.copy(pixels,
        ((row * size + y) * width + col * size) * 4, y * rowBytes, (y + 1) * rowBytes)
      return {clip_topleft: [col * size, row * size, size, size],
        foot_pivot_topleft: [col * size + 40, row * size + 72], opaque_rows: raster.opaqueRows(frame),
        start: times[row], end: times[row + 1]}
    })
  }
  await saveAtlas(pixels, metadata)
  await raster.png(pixels, width, height, path.join(review, 'heavy-attack-sheet.png'), 2)
}

async function readCell(name, col, row) {
  const sharp = require('sharp')
  return sharp(path.join(assets, name)).extract({left: col * size, top: row * size, width: size, height: size})
    .ensureAlpha().raw().toBuffer()
}

run().catch(error => { console.error(error); process.exitCode = 1 })
