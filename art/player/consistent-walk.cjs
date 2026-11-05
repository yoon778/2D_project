// Offline master-pixel extraction and projected-joint baking. Requires sharp.
// Run from the project root: node art/player/consistent-walk.cjs front_right
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const config = require('./consistent-rig.json')

const size = config.cellSize
const root = path.resolve(__dirname, '../..')

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

// Preserve the painted limb width; fit only its projected joint axis.
function segment(target, source, sourceStart, sourceEnd, start, end) {
  const sx = sourceEnd[0] - sourceStart[0], sy = sourceEnd[1] - sourceStart[1]
  const dx = end[0] - start[0], dy = end[1] - start[1]
  const sl = Math.hypot(sx, sy), dl = Math.hypot(dx, dy)
  const su = [sx / sl, sy / sl], du = [dx / dl, dy / dl]
  paint(target, source, (x, y) => {
    const px = x - start[0], py = y - start[1]
    const along = (px * du[0] + py * du[1]) * sl / dl
    const across = -px * du[1] + py * du[0]
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

function joints(rig, leg, frame) {
  const phase = (frame + leg.phase) % 8
  const length = Math.hypot(...rig.worldFacing)
  const ground = [rig.worldFacing[0] / length, rig.worldFacing[1] / length * 0.6]
  const travel = config.strideNative[phase], bend = config.kneeForward[phase]
  const hip = [leg.hip[0], leg.hip[1] + config.bodyDrop[frame]]
  const ankle = [leg.ankle[0] + ground[0] * travel,
    leg.ankle[1] + ground[1] * travel - config.swingLift[phase]]
  const ratio = Math.hypot(leg.knee[0] - leg.hip[0], leg.knee[1] - leg.hip[1])
    / Math.hypot(leg.ankle[0] - leg.hip[0], leg.ankle[1] - leg.hip[1])
  const knee = [hip[0] + (ankle[0] - hip[0]) * ratio + ground[0] * bend,
    hip[1] + (ankle[1] - hip[1]) * ratio - bend * 0.24]
  return {phase, hip, knee, ankle, pitch: config.bootPitchDegrees[phase] * ground[0]}
}

async function png(pixels, width, height, destination, scale = 1) {
  await sharp(pixels, {raw: {width, height, channels: 4}})
    .resize(width * scale, height * scale, {kernel: 'nearest'}).png().toFile(destination)
}

async function bake(facing) {
  const rig = config.facings[facing]
  if (!rig) throw new Error(`No approved rig for ${facing}`)
  const [left, top, width, height] = rig.sourceCell
  const source = await sharp(path.join(__dirname, config.master))
    .extract({left, top, width, height}).ensureAlpha().raw().toBuffer()
  const parts = {bat: cut(source, rig.batMask), body: Buffer.from(source)}
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const remove = maskContains(source, x, y, rig.lowerBodyMask) || parts.bat[(y * size + x) * 4 + 3]
    if (remove && !maskContains(source, x, y, rig.bodyKeepMask)) {
      parts.body.fill(0, (y * size + x) * 4, (y * size + x + 1) * 4)
    }
  }
  for (const side of ['right', 'left']) {
    parts[side] = Object.fromEntries(['thigh', 'shin', 'boot'].map(
      part => [part, cut(source, legMaterial(rig, side, part)[part + 'Mask'])]))
  }
  const poses = [], poseJoints = []
  const farLeg = rig.nearLeg === 'right' ? 'left' : 'right'
  for (let frame = 0; frame < 8; frame++) {
    const pixels = Buffer.alloc(source.length), frameJoints = {}
    if (rig.batBehindLegs) translate(pixels, parts.bat, 0, config.bodyDrop[frame])
    for (const side of [farLeg, rig.nearLeg]) {
      const legPixels = Buffer.alloc(source.length)
      const leg = rig.legs[side], points = joints(rig, leg, frame)
      const bootMaterial = legMaterial(rig, side, 'boot')
      const shinMaterial = legMaterial(rig, side, 'shin')
      const thighMaterial = legMaterial(rig, side, 'thigh')
      frameJoints[side] = points
      boot(legPixels, parts[side].boot, bootMaterial.ankle, points.ankle, points.pitch)
      segment(legPixels, parts[side].shin, shinMaterial.knee, shinMaterial.ankle, points.knee, points.ankle)
      segment(legPixels, parts[side].thigh, thighMaterial.hip, thighMaterial.knee, points.hip, points.knee)
      restoreLegOutline(legPixels, points.hip)
      translate(pixels, legPixels, 0, 0)
    }
    if (!rig.batBehindLegs) translate(pixels, parts.bat, 0, config.bodyDrop[frame])
    translate(pixels, parts.body, 0, config.bodyDrop[frame])
    poses.push(pixels)
    poseJoints.push(frameJoints)
  }
  // Idle is a byte-exact source-cell copy, independent of the rig render.
  poses.push(source)
  const atlas = Buffer.alloc(size * 4 * size * 3 * 4)
  for (let frame = 0; frame < poses.length; frame++) for (let y = 0; y < size; y++) {
    const to = ((Math.floor(frame / 4) * size + y) * size * 4 + frame % 4 * size) * 4
    poses[frame].copy(atlas, to, y * size * 4, (y + 1) * size * 4)
  }
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

async function main() {
  for (const file of ['consistent-front-back.json', 'consistent-side.json', 'consistent-diagonal.json']) {
    try {
      Object.assign(config.facings, JSON.parse(await fs.readFile(path.join(__dirname, file), 'utf8')))
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
  }
  const facing = process.argv.slice(2).find(arg => !arg.startsWith('--'))
  const facings = facing ? [facing] : Object.keys(config.facings)
  for (const facing of facings) await bake(facing)
}
main().catch(error => {console.error(error); process.exitCode = 1})
