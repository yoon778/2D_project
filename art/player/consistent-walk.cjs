// Offline master-pixel extraction and projected-joint baking. Requires sharp.
// Run from the project root: node art/player/consistent-walk.cjs front_right
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const config = require('./consistent-rig.json')

const size = config.cellSize
const root = path.resolve(__dirname, '../..')
const walkFragments = {
  front_left: {phases: [3, 4, 5], columns: [[32, 67, 70], [31, 68, 70]]},
  back_left: {phases: [0, 1, 6, 7], columns: [[47, 57, 60]]},
}

function inside(x, y, polygon) {
  let hit = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [ax, ay] = polygon[i], [bx, by] = polygon[j]
    if ((ay > y) !== (by > y) && x < (bx - ax) * (y - ay) / (by - ay) + ax) hit = !hit
  }
  return hit
}

function maskContains(source, x, y, mask) {
  if (!mask) return false
  let hit
  if (Array.isArray(mask)) hit = inside(x + 0.5, y + 0.5, mask)
  else if (mask.rows) {
    const row = mask.rows[y]
    const spans = row && (Array.isArray(row[0]) ? row : [row])
    hit = spans && spans.some(([left, right]) => x >= left && x <= right)
  } else hit = inside(x + 0.5, y + 0.5, mask.polygon)
  if (!hit || !mask.colors) return Boolean(hit)
  const offset = (y * size + x) * 4
  return mask.colors.includes(source.subarray(offset, offset + 3).toString('hex'))
}

function cut(source, mask) {
  const pixels = Buffer.alloc(source.length)
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    if (maskContains(source, x, y, mask)) {
      const offset = (y * size + x) * 4
      source.copy(pixels, offset, offset, offset + 4)
    }
  }
  // Restore only explicitly bounded, occluded material from the same view.
  for (const patch of mask?.copies || []) {
    if (!mask.restoreRows) throw new Error('Material copies require restoreRows bounds')
    const [sx, sy, width, height] = patch.source, [tx, ty] = patch.target
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const fromX = sx + x, fromY = sy + y, toX = tx + x, toY = ty + y
      if ([fromX, fromY, toX, toY].some(value => value < 0 || value >= size)) continue
      if (!maskContains(source, toX, toY, {rows: mask.restoreRows})) continue
      const from = (fromY * size + fromX) * 4, to = (toY * size + toX) * 4
      if (pixels[to + 3] || !source[from + 3]) continue
      if (mask.colors && !mask.colors.includes(source.subarray(from, from + 3).toString('hex'))) continue
      source.copy(pixels, to, from, from + 4)
    }
  }
  return pixels
}

function legMaterial(rig, side, part) {
  const leg = rig.legs[side]
  return rig.legs[leg[part + 'TextureFrom'] || leg.textureFrom || side]
}

function paint(target, source, inverse) {
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const [sx, sy] = inverse(x, y).map(Math.round)
    if (sx < 0 || sy < 0 || sx >= size || sy >= size) continue
    const from = (sy * size + sx) * 4
    if (source[from + 3]) source.copy(target, (y * size + x) * 4, from, from + 4)
  }
}

function translate(target, source, dx, dy) {
  paint(target, source, (x, y) => [x - dx, y - dy])
}

function restoreLegOutline(pixels, hip) {
  const dark = new Set(['15141b', '242633', '392b29'])
  // Recolor inside the assembled leg's existing alpha; keep the pelvis join open.
  for (let y = Math.floor(hip[1]) + 3; y < size; y++) for (let x = 0; x < size; x++) {
    const offset = (y * size + x) * 4
    if (!pixels[offset + 3] || dark.has(pixels.subarray(offset, offset + 3).toString('hex'))) continue
    const exposed = [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]].some(([nx, ny]) =>
      nx < 0 || nx >= size || ny < 0 || ny >= size || !pixels[(ny * size + nx) * 4 + 3])
    if (exposed) pixels.set([0x15, 0x14, 0x1b], offset)
  }
}

function restoreHipOutline(pixels, band, protectedPixels, sideEdgesOnly = false) {
  const navy = new Set(['242633', '323648', '42495f', '555d77', '69728e'])
  const directions = sideEdgesOnly ? [[-1, 0], [1, 0]] : [[-1, 0], [1, 0], [0, -1], [0, 1]]
  for (let y = Math.max(0, band[0]); y <= Math.min(size - 1, band[1]); y++) for (let x = 0; x < size; x++) {
    const offset = (y * size + x) * 4
    if (!pixels[offset + 3] || protectedPixels?.[offset + 3]
      || !navy.has(pixels.subarray(offset, offset + 3).toString('hex'))) continue
    const exposed = directions.some(([dx, dy]) => {
      const nx = x + dx, ny = y + dy
      return nx < 0 || nx >= size || ny < 0 || ny >= size || !pixels[(ny * size + nx) * 4 + 3]
    })
    if (exposed) pixels.set([0x15, 0x14, 0x1b], offset)
  }
}

// Fit the projected joint axis. The side-walk rig can restore width lost to occlusion.
function segment(target, source, sourceStart, sourceEnd, start, end, widthScale = 1) {
  const sx = sourceEnd[0] - sourceStart[0], sy = sourceEnd[1] - sourceStart[1]
  const dx = end[0] - start[0], dy = end[1] - start[1]
  const sl = Math.hypot(sx, sy), dl = Math.hypot(dx, dy)
  const su = [sx / sl, sy / sl], du = [dx / dl, dy / dl]
  paint(target, source, (x, y) => {
    const px = x - start[0], py = y - start[1]
    const along = (px * du[0] + py * du[1]) * sl / dl
    const across = (-px * du[1] + py * du[0]) / widthScale
    return [sourceStart[0] + su[0] * along - su[1] * across,
      sourceStart[1] + su[1] * along + su[0] * across]
  })
}

function boot(target, source, anchor, ankle, degrees) {
  const radians = degrees * Math.PI / 180
  const c = Math.cos(radians), s = Math.sin(radians)
  paint(target, source, (x, y) => {
    const dx = x - ankle[0], dy = y - ankle[1]
    return [anchor[0] + c * dx + s * dy, anchor[1] - s * dx + c * dy]
  })
}

function drawBat(target, source, rotation, drop) {
  if (!rotation) return translate(target, source, 0, drop)
  const {pivot, targetPivot = pivot, degrees, axisEnd, lengthScale = 1} = rotation
  const grip = [targetPivot[0], targetPivot[1] + drop]
  if (!axisEnd || lengthScale === 1) return boot(target, source, pivot, grip, degrees)
  const radians = degrees * Math.PI / 180
  const dx = (axisEnd[0] - pivot[0]) * lengthScale, dy = (axisEnd[1] - pivot[1]) * lengthScale
  const tip = [grip[0] + Math.cos(radians) * dx - Math.sin(radians) * dy,
    grip[1] + Math.sin(radians) * dx + Math.cos(radians) * dy]
  segment(target, source, pivot, axisEnd, grip, tip)
}

function applyLegFacet(pixels, facet, allowedPixels) {
  const color = [0, 2, 4].map(offset => parseInt(facet.to.slice(offset, offset + 2), 16))
  for (let y = facet.y[0]; y <= facet.y[1]; y++) for (let x = facet.x[0]; x <= facet.x[1]; x++) {
    const offset = (y * size + x) * 4
    if (allowedPixels && !allowedPixels[offset + 3]) continue
    if (pixels[offset + 3] && pixels.subarray(offset, offset + 3).toString('hex') === facet.from) {
      pixels.set(color, offset)
    }
  }
}

function drawLeg(rig, parts, side, points, hipBand, {widthScale = 1, shinOverlap = 0} = {}) {
  const pixels = Buffer.alloc(size * size * 4)
  const bootMaterial = legMaterial(rig, side, 'boot')
  const shinMaterial = legMaterial(rig, side, 'shin')
  const thighMaterial = legMaterial(rig, side, 'thigh')
  boot(pixels, parts[side].boot, bootMaterial.ankle, points.ankle, points.pitch)
  const shin = points.ankle.map((value, axis) => value - points.knee[axis])
  const length = Math.hypot(...shin)
  const shinEnd = points.ankle.map((value, axis) => value + shin[axis] * shinOverlap / length)
  segment(pixels, parts[side].shin, shinMaterial.knee, shinMaterial.ankle, points.knee, shinEnd, widthScale)
  segment(pixels, parts[side].thigh, thighMaterial.hip, thighMaterial.knee, points.hip, points.knee, widthScale)
  restoreLegOutline(pixels, points.hip)
  if (hipBand) restoreHipOutline(pixels, hipBand, null, true)
  return pixels
}

function joints(rig, leg, frame) {
  const phase = (frame + leg.phase) % 8
  const length = Math.hypot(...rig.worldFacing)
  const ground = [rig.worldFacing[0] / length, rig.worldFacing[1] / length * 0.6]
  const travel = config.strideNative[phase]
  const bend = (rig.walkCycle?.kneeForward ?? config.kneeForward)[phase]
  const lift = (rig.walkCycle?.swingLift ?? config.swingLift)[phase]
  const hip = [leg.hip[0], leg.hip[1] + config.bodyDrop[frame]]
  const ankle = [leg.ankle[0] + ground[0] * travel + (leg.passingOffsetX?.[phase] ?? 0),
    leg.ankle[1] + ground[1] * travel - lift + (leg.depthOffset ?? 0)]
  const ratio = Math.hypot(leg.knee[0] - leg.hip[0], leg.knee[1] - leg.hip[1])
    / Math.hypot(leg.ankle[0] - leg.hip[0], leg.ankle[1] - leg.hip[1])
  const knee = [hip[0] + (ankle[0] - hip[0]) * ratio + ground[0] * bend,
    hip[1] + (ankle[1] - hip[1]) * ratio - bend * 0.24]
  return {phase, hip, knee, ankle, pitch: config.bootPitchDegrees[phase] * ground[0]}
}

function extractLegParts(source, rig) {
  const parts = {}
  for (const side of ['right', 'left']) {
    parts[side] = Object.fromEntries(['thigh', 'shin', 'boot'].map(
      part => [part, cut(source, legMaterial(rig, side, part)[part + 'Mask'])]))
  }
  if (rig.legFacet) for (const part of ['thigh', 'shin']) {
    applyLegFacet(parts[rig.legFacet.side][part], rig.legFacet)
  }
  return parts
}

function shiftWalkJoints(points, [dx, dy]) {
  // Follow the torso at the hip while keeping the ankle on its walk anchor.
  const kneeWeight = Math.max(0, Math.min(1, (63 - points.knee[1]) / 10))
  points.hip = [points.hip[0] + dx, points.hip[1] + dy]
  points.knee = [points.knee[0] + dx * kneeWeight, points.knee[1] + dy * kneeWeight]
}

async function prepareWalkMirror(rig, facings) {
  if (!rig.walkMirrorFrom) return null
  const donor = facings[rig.walkMirrorFrom]
  const [left, top, width, height] = donor.sourceCell
  const source = await sharp(path.join(__dirname, config.master))
    .extract({left, top, width, height}).ensureAlpha().raw().toBuffer()
  const parts = extractLegParts(source, donor)
  const phaseOffset = rig.legs[rig.nearLeg].phase - donor.legs[donor.nearLeg].phase
  const donorFar = donor.nearLeg === 'right' ? 'left' : 'right'
  const hips = Object.values(donor.legs).map(leg => leg.hip[1])
  const hipBand = donor.hipOutline ? [Math.min(...hips) - 2, Math.max(...hips) + 5] : null
  const axis = config.root[0] * 2
  return (side, frame, weight) => {
    const donorSide = side === rig.nearLeg ? donor.nearLeg : donorFar
    const leg = donor.legs[donorSide]
    const donorFrame = (frame + phaseOffset + 8) % 8
    const points = joints(donor, leg, donorFrame)
    const drop = config.bodyDrop[donorFrame]
    const band = hipBand?.map(y => y + drop)
    if (weight) shiftWalkJoints(points, [-weight[0], weight[1]])
    const donorPixels = drawLeg(donor, parts, donorSide, points, band, leg.walkFit)
    // Reflect about the common ground pivot, then align the reflected hip in X.
    const offset = rig.legs[side].hip[0] - (axis - leg.hip[0])
    const reflect = x => axis - x + offset
    const pixels = Buffer.alloc(donorPixels.length)
    paint(pixels, donorPixels, (x, y) => [reflect(x), y])
    for (const name of ['hip', 'knee', 'ankle']) points[name][0] = reflect(points[name][0])
    points.pitch = -points.pitch
    return {pixels, points}
  }
}

async function png(pixels, width, height, destination, scale = 1) {
  await sharp(pixels, {raw: {width, height, channels: 4}})
    .resize(width * scale, height * scale, {kernel: 'nearest'}).png().toFile(destination)
}

async function bake(facing, {renderOnly = false, overrides} = {}) {
  const approved = config.facings[facing]
  if (!approved) throw new Error(`No approved rig for ${facing}`)
  const rig = overrides ? {...approved, ...overrides} : approved
  const [left, top, width, height] = rig.sourceCell
  const source = await sharp(path.join(__dirname, config.master))
    .extract({left, top, width, height}).ensureAlpha().raw().toBuffer()
  const originalBat = cut(source, rig.batMask)
  const parts = {bat: originalBat, body: Buffer.from(source)}
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const remove = maskContains(source, x, y, rig.lowerBodyMask) || parts.bat[(y * size + x) * 4 + 3]
    if (remove && !maskContains(source, x, y, rig.bodyKeepMask)) {
      parts.body.fill(0, (y * size + x) * 4, (y * size + x + 1) * 4)
    }
  }
  const carryArm = rig.carryArm && cut(parts.body, rig.carryArm.mask)
  if (carryArm) {
    for (let offset = 0; offset < carryArm.length; offset += 4) {
      if (carryArm[offset + 3]) parts.body.fill(0, offset, offset + 4)
    }
    const {pivot, degrees} = rig.carryArm
    boot(parts.body, carryArm, pivot, pivot, degrees)
  }
  if (rig.batSourceFacing) {
    const donor = config.facings[rig.batSourceFacing]
    const [left, top, width, height] = donor.sourceCell
    const material = await sharp(path.join(__dirname, config.master))
      .extract({left, top, width, height}).ensureAlpha().raw().toBuffer()
    parts.bat = cut(material, donor.batMask)
  }
  Object.assign(parts, extractLegParts(source, rig))
  const mirroredLeg = await prepareWalkMirror(rig, config.facings)
  const poses = [], poseJoints = []
  const farLeg = rig.nearLeg === 'right' ? 'left' : 'right'
  const batBehindLegs = rig.walkBatBehindLegs ?? rig.batBehindLegs
  const carryRotation = rig.carryBatDegrees === undefined ? rig.batRotation : {...rig.batRotation, degrees: rig.carryBatDegrees}
  const heldHand = rig.hipOutline ? cut(source, rig.bodyKeepMask) : null
  const fragment = walkFragments[facing]
  for (let frame = 0; frame < 8; frame++) {
    const pixels = Buffer.alloc(source.length), frameJoints = {}
    const drop = config.bodyDrop[frame]
    const hipBand = rig.hipOutline ? [Math.min(rig.legs.right.hip[1], rig.legs.left.hip[1]) - 2 + drop,
      Math.max(rig.legs.right.hip[1], rig.legs.left.hip[1]) + 5 + drop] : null
    const legCoverage = hipBand ? Buffer.alloc(source.length) : null
    const batPixels = Buffer.alloc(source.length)
    drawBat(batPixels, parts.bat, carryRotation, drop)
    if (batBehindLegs) translate(pixels, batPixels, 0, 0)
    for (const side of [farLeg, rig.nearLeg]) {
      const leg = rig.legs[side], mirror = mirroredLeg?.(side, frame)
      const points = mirror?.points ?? joints(rig, leg, frame)
      frameJoints[side] = points
      // Side edges separate the legs without drawing a horizontal hip cut line.
      const legPixels = mirror?.pixels ?? drawLeg(rig, parts, side, points, hipBand, leg.walkFit)
      translate(pixels, legPixels, 0, 0)
      if (legCoverage) translate(legCoverage, legPixels, 0, 0)
    }
    if (!batBehindLegs) translate(pixels, batPixels, 0, 0)
    translate(pixels, parts.body, 0, config.bodyDrop[frame])
    if (hipBand) {
      const protectedPixels = Buffer.alloc(source.length)
      translate(protectedPixels, heldHand, 0, drop)
      for (let y = hipBand[0]; y <= hipBand[1]; y++) for (let x = 0; x < size; x++) {
        const to = (y * size + x) * 4, from = ((y - drop) * size + x) * 4
        if (batPixels[to + 3] && !parts.body[from + 3]
          && (!batBehindLegs || !legCoverage[to + 3])) protectedPixels[to + 3] = 255
      }
      // Fixed body pixels can own the exposed hip edge after leg compositing.
      restoreHipOutline(pixels, hipBand, protectedPixels)
    }
    for (const [y, left, right, color] of rig.walkHipSeams?.[frame] ?? []) {
      const pixel = Buffer.from(color + 'ff', 'hex')
      pixels.fill(pixel, (y * size + left) * 4, (y * size + right + 1) * 4)
    }
    // Clear only the verified outline remnants after pose compositing.
    if (fragment?.phases.includes(frame)) {
      for (const [x, top, bottom] of fragment.columns) {
        for (let y = top + drop; y <= bottom + drop; y++) {
          const p = (y * size + x) * 4
          pixels.fill(0, p, p + 4)
        }
      }
    }
    poses.push(pixels)
    poseJoints.push(frameJoints)
  }
  let idle = source
  if (rig.batRotation) {
    if (rig.batBehindLegs) {
      const foreground = Buffer.from(source)
      for (let offset = 0; offset < foreground.length; offset += 4) {
        if (originalBat[offset + 3] && !heldHand?.[offset + 3]) foreground.fill(0, offset, offset + 4)
      }
      idle = Buffer.alloc(source.length)
      drawBat(idle, parts.bat, carryRotation, 0)
      translate(idle, foreground, 0, 0)
    } else {
      const uncovered = Buffer.alloc(source.length)
      const hipBand = rig.hipOutline ? [Math.min(rig.legs.right.hip[1], rig.legs.left.hip[1]) - 2,
        Math.max(rig.legs.right.hip[1], rig.legs.left.hip[1]) + 5] : null
      for (const side of [farLeg, rig.nearLeg]) {
        const leg = rig.legs[side]
        translate(uncovered, drawLeg(rig, parts, side, {...leg, pitch: 0}, hipBand), 0, 0)
      }
      idle = Buffer.from(source)
      for (let offset = 0; offset < idle.length; offset += 4) {
        if ((originalBat[offset + 3] && !heldHand?.[offset + 3]) || carryArm?.[offset + 3]) {
          uncovered.copy(idle, offset, offset, offset + 4)
        }
      }
      drawBat(idle, parts.bat, carryRotation, 0)
      translate(idle, parts.body, 0, 0)
    }
    if (rig.legFacet) applyLegFacet(idle, rig.legFacet, parts[rig.legFacet.side].thigh)
  }
  // Other views retain their exact approved idle; a rotated bat restores only its old footprint.
  poses.push(idle)
  const atlas = Buffer.alloc(size * 4 * size * 3 * 4)
  for (let frame = 0; frame < poses.length; frame++) for (let y = 0; y < size; y++) {
    const to = ((Math.floor(frame / 4) * size + y) * size * 4 + frame % 4 * size) * 4
    poses[frame].copy(atlas, to, y * size * 4, (y + 1) * size * 4)
  }
  if (renderOnly) return atlas
  const slug = facing.replaceAll('_', '-')
  const output = path.join(root, `game/assets/player/r1-consistent-${slug}-20261105.png`)
  const review = path.join(root, 'output/review/R1-C8-WALK-art', slug)
  const extracted = path.join(__dirname, 'consistent-parts', slug)
  await png(atlas, size * 4, size * 3, output)
  if (process.argv.includes('--atlas-only')) {
    console.log(JSON.stringify({facing, output}))
    return
  }
  await fs.mkdir(review, {recursive: true})
  await fs.mkdir(extracted, {recursive: true})
  await png(atlas, size * 4, size * 3, path.join(review, 'atlas-4x.png'), 4)
  for (const name of ['body', 'bat']) await png(parts[name], size, size, path.join(extracted, `${name}.png`))
  for (const side of ['right', 'left']) for (const part of ['thigh', 'shin', 'boot']) {
    await png(parts[side][part], size, size, path.join(extracted, `${side}-${part}.png`))
  }
  const maskParts = [parts.body, parts.bat, ...['right', 'left'].flatMap(side =>
    ['thigh', 'shin', 'boot'].map(part => parts[side][part]))]
  const masks = Buffer.alloc(size * 4 * size * 2 * 4)
  for (let part = 0; part < maskParts.length; part++) for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) if (maskParts[part][(y * size + x) * 4 + 3]) {
      const to = ((Math.floor(part / 4) * size + y) * size * 4 + part % 4 * size + x) * 4
      masks.set(part < 2 ? [240, 190, 100, 255] : part < 5 ? [245, 100, 110, 255] : [80, 190, 245, 255], to)
    }
  }
  await png(masks, size * 4, size * 2, path.join(review, 'masks-4x.png'), 4)
  await png(parts.body, size, size, path.join(review, 'body-8x.png'), 8)
  await fs.writeFile(path.join(review, 'joints.json'), JSON.stringify({facing, sourceCell: rig.sourceCell,
    root: config.root, referenceHeight: config.referenceHeight, frameOrder: ['walk1', 'walk2', 'walk3',
      'walk4', 'walk5', 'walk6', 'walk7', 'walk8', 'idle'], poses: poseJoints}, null, 2) + '\n')
  const animationFrames = await Promise.all(poses.slice(0, 8).map(pixels =>
    sharp(pixels, {raw: {width: size, height: size, channels: 4}})
      .resize(size * 4, size * 4, {kernel: 'nearest'}).raw().toBuffer()))
  await sharp(Buffer.concat(animationFrames), {
    raw: {width: size * 4, height: size * 8 * 4, channels: 4, pageHeight: size * 4}})
    .gif({loop: 0, delay: Array(8).fill(Math.round(64000 / 90 / 8)), effort: 3})
    .toFile(path.join(review, 'walk-4x.gif'))
  console.log(JSON.stringify({facing, output, review, extracted}))
}

async function loadRigs() {
  for (const file of ['consistent-front-back.json', 'consistent-side.json', 'consistent-diagonal.json']) {
    try {
      Object.assign(config.facings, JSON.parse(await fs.readFile(path.join(__dirname, file), 'utf8')))
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
  }
}

async function renderWalkAtlas(facing, overrides) {
  await loadRigs()
  return bake(facing, {renderOnly: true, overrides})
}

async function main() {
  await loadRigs()
  const facing = process.argv.slice(2).find(arg => !arg.startsWith('--'))
  const facings = facing ? [facing] : Object.keys(config.facings)
  for (const facing of facings) await bake(facing)
}
module.exports = {drawLeg, joints, prepareWalkMirror, renderWalkAtlas, shiftWalkJoints}
if (require.main === module) main().catch(error => {console.error(error); process.exitCode = 1})
