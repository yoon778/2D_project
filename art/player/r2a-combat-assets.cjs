// Offline R2-A assets: approved FR body plus articulated right arm and held bat.
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const {shiftWeight} = require('../attack-weight.cjs')
const root = path.resolve(__dirname, '../..')
const size = 96, sourceSize = 80, offset = 8
const keys = [
  {name: 'anticipate_1', label: '준비 1', elbow: [22, 38], wrist: [21, 32], hand: 145, bat: 120, behind: true},
  {name: 'anticipate_2', label: '준비 2', elbow: [25, 24], wrist: [31, 23], hand: -105, bat: -155, behind: true},
  {name: 'hit', label: '타격', elbow: [37, 35], wrist: [45, 37], hand: -70, bat: -45},
  {name: 'follow', label: '후속', elbow: [37, 43], wrist: [41, 50], hand: -15, bat: -10},
  {name: 'recover', label: '회복', elbow: [28, 41], wrist: [30, 48], hand: 0, bat: 8}
]
const rest = {elbow: [27, 40], wrist: [28, 46], hand: 0, bat: 0}
function shortAngle(a, b, t) {return a + ((b - a + 540) % 360 - 180) * t}
function between(a, b, t, name, label) {
  const bone = (from, to, origin) => {
    const angle = shortAngle(Math.atan2(from[1], from[0]) * 180 / Math.PI, Math.atan2(to[1], to[0]) * 180 / Math.PI, t) * Math.PI / 180
    const length = Math.hypot(...from) * (1 - t) + Math.hypot(...to) * t
    return [origin[0] + Math.cos(angle) * length, origin[1] + Math.sin(angle) * length]
  }
  const elbow = bone([a.elbow[0] - 27, a.elbow[1] - 32], [b.elbow[0] - 27, b.elbow[1] - 32], [27, 32])
  const wrist = bone([a.wrist[0] - a.elbow[0], a.wrist[1] - a.elbow[1]], [b.wrist[0] - b.elbow[0], b.wrist[1] - b.elbow[1]], elbow)
  return {name, label, elbow, wrist, hand: shortAngle(a.hand, b.hand, t), bat: shortAngle(a.bat, b.bat, t), behind: Boolean(a.behind)}
}
const poses = [keys[0], between(keys[0], keys[1], .5, 'anticipate_mid', '준비 중간'),
  keys[1], between(keys[1], keys[2], .5, 'swing_mid', '휘두르기 중간'),
  keys[2], between(keys[2], keys[3], .5, 'hit_follow_mid', '타격 후속 중간'),
  keys[3], between(keys[3], keys[4], .5, 'follow_recover_mid', '후속 회복 중간'),
  keys[4], between(keys[4], rest, (.425 - .37) / (.54 - .37), 'recover_return_1', '복귀 중간 1'),
  between(keys[4], rest, (.48 - .37) / (.54 - .37), 'recover_return_2', '복귀 중간 2'),
  {name: 'return', label: '복귀'}]
const times = [0, .045, .09, .135, .18, .225, .27, .32, .37, .425, .48, .54, .60]
const navy = ['15141b', '242633', '323648', '42495f', '555d77', '69728e']
const masks = {
  upper: [[23, 31], [30, 31], [30, 41], [24, 41], [23, 38]],
  fore: [[24, 38], [30, 38], [31, 46], [25, 46], [24, 44]],
  hand: [[25, 46], [33, 46], [33, 52], [25, 52]],
  bat: require('./consistent-rig.json').facings.front_right.batMask
}
function inside(x, y, p) {
  let hit = false
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [a, b] = p[i], [c, d] = p[j]
    if ((b > y) !== (d > y) && x < (c - a) * (y - b) / (d - b) + a) hit = !hit
  }
  return hit
}
function cut(src, polygon, colors) {
  const b = Buffer.alloc(src.length)
  for (let y = 0; y < 80; y++) for (let x = 0; x < 80; x++) {
    const p = (y * 80 + x) * 4
    if (inside(x + .5, y + .5, polygon) && (!colors || colors.includes(src.subarray(p, p + 3).toString('hex')))) src.copy(b, p, p, p + 4)
  }
  return b
}
function paint(dst, src, inverse) {
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const [sx, sy] = inverse(x - offset, y - offset).map(Math.round)
    if (sx < 0 || sy < 0 || sx >= sourceSize || sy >= sourceSize) continue
    const p = (sy * 80 + sx) * 4
    if (src[p + 3]) src.copy(dst, (y * size + x) * 4, p, p + 4)
  }
}
function segment(dst, src, a, b, c, d) {
  const dx = b[0] - a[0], dy = b[1] - a[1], tx = d[0] - c[0], ty = d[1] - c[1]
  const sl = Math.hypot(dx, dy), tl = Math.hypot(tx, ty), su = [dx / sl, dy / sl], tu = [tx / tl, ty / tl]
  paint(dst, src, (x, y) => {
    const px = x - c[0], py = y - c[1], along = (px * tu[0] + py * tu[1]) * sl / tl, across = -px * tu[1] + py * tu[0]
    return [a[0] + su[0] * along - su[1] * across, a[1] + su[1] * along + su[0] * across]
  })
}
function rotate(dst, src, anchor, target, degrees) {
  const angle = degrees * Math.PI / 180, c = Math.cos(angle), s = Math.sin(angle)
  paint(dst, src, (x, y) => [anchor[0] + c * (x - target[0]) + s * (y - target[1]), anchor[1] - s * (x - target[0]) + c * (y - target[1])])
}
async function png(b, width, height, file, scale = 1) {
  await sharp(b, {raw: {width, height, channels: 4}}).resize(width * scale, height * scale, {kernel: 'nearest'}).png().toFile(file)
}
function overlay(dst, src, width, height, left = 0, top = 0) {
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const xx = x + left, yy = y + top, from = (y * width + x) * 4
    if (xx < 0 || yy < 0 || xx >= size || yy >= size || !src[from + 3]) continue
    src.copy(dst, (yy * size + xx) * 4, from, from + 4)
  }
}
function renderArm(parts, pose) {
  const arm = Buffer.alloc(size * size * 4), weapon = Buffer.alloc(arm.length)
  const [dx, dy] = pose.weight || [0, 0]
  const shoulder = [27 + dx, 32 + dy]
  const angle = pose.hand * Math.PI / 180
  const grip = [pose.wrist[0] + Math.cos(angle) - 6 * Math.sin(angle), pose.wrist[1] + Math.sin(angle) + 6 * Math.cos(angle)]
  segment(arm, parts.upper, [27, 32], [27, 40], shoulder, pose.elbow)
  segment(arm, parts.fore, [27, 40], [28, 46], pose.elbow, pose.wrist)
  rotate(arm, parts.hand, [28, 46], pose.wrist, pose.hand)
  rotate(weapon, parts.bat, [29, 52], grip, pose.bat)
  return {arm, weapon, grip}
}
async function attackWalk(dest, review, parts, attackPoses = poses) {
  const {drawLeg, joints} = require('./consistent-walk.cjs')
  const walk = require('./consistent-rig.json'), rig = walk.facings.front_right
  const legs = {}
  for (const side of ['right', 'left']) {
    legs[side] = {}
    for (const name of ['thigh', 'shin', 'boot']) legs[side][name] = await sharp(
      path.join(__dirname, 'consistent-parts/front-right', `${side}-${name}.png`)).ensureAlpha().raw().toBuffer()
  }
  const upper = await sharp(path.join(__dirname, 'consistent-parts/front-right/body.png')).ensureAlpha().raw().toBuffer()
  for (let p = 0; p < upper.length; p += 4) {
    if (parts.upper[p + 3] || parts.fore[p + 3] || parts.hand[p + 3]) upper.fill(0, p, p + 4)
  }
  const upperCell = Buffer.alloc(size * size * 4)
  paint(upperCell, upper, (x, y) => [x, y])
  const walkPng = await sharp(path.join(root, 'game/assets/player/r1-consistent-front-right-20261105.png')).ensureAlpha().raw().toBuffer()
  const atlasHeight = attackPoses.length * size, atlas = Buffer.alloc(768 * atlasHeight * 4), cells = [], frames = []
  for (const [attack, pose] of attackPoses.entries()) {
    const {arm, weapon} = pose.elbow ? renderArm(parts, pose) : {}
    const torso = pose.weight ? shiftWeight(upperCell, size, offset, pose.weight, 49, 60) : upperCell
    for (let phase = 0; phase < 8; phase++) {
      const b = Buffer.alloc(size * size * 4), drop = walk.bodyDrop[phase]
      if (!pose.elbow) {
        // The attack-to-walk transition uses the exact already-approved walk pixels.
        for (let y = 0; y < 80; y++) {
          const from = ((Math.floor(phase / 4) * 80 + y) * 320 + phase % 4 * 80) * 4
          walkPng.copy(b, ((y + 8) * size + 8) * 4, from, from + 320)
        }
      } else {
        if (pose.behind) overlay(b, weapon, size, size, 0, drop)
        const legCell = Buffer.alloc(b.length)
        for (const side of ['left', 'right']) {
          overlay(legCell, drawLeg(rig, legs, side, joints(rig, rig.legs[side], phase), null), 80, 80, 8, 8)
        }
        const hips = pose.weight ? shiftWeight(legCell, size, offset + drop, pose.weight, 49, 60) : legCell
        overlay(b, hips, size, size)
        if (pose.behind) overlay(b, arm, size, size, 0, drop)
        overlay(b, torso, size, size, 0, drop)
        if (!pose.behind) {
          overlay(b, arm, size, size, 0, drop)
          overlay(b, weapon, size, size, 0, drop)
        }
      }
      const index = attack * 8 + phase
      cells.push(b)
      for (let y = 0; y < size; y++) b.copy(atlas, ((attack * size + y) * 768 + phase * size) * 4, y * size * 4, (y + 1) * size * 4)
      frames.push({name: `${pose.name}_walk${phase + 1}`, attack_index: attack, walk_frame_index: phase + 1,
        clip_topleft: [phase * size, attack * size, size, size],
        foot_pivot_topleft: [phase * size + 48, attack * size + 80]})
    }
  }
  if (!dest) return {atlas, cells, frames}
  await fs.mkdir(review, {recursive: true})
  const image = 'r2aw-attack-walk-front-right-20261106.png'
  await png(atlas, 768, atlasHeight, path.join(dest, image))
  await png(atlas, 768, atlasHeight, path.join(review, 'attack-walk-96-2x.png'), 2)
  const sample = Buffer.alloc(384 * 288 * 4), sequence = []
  for (let a = 0; a < poses.length; a++) {
    const elapsed = (times[a] + times[a + 1]) / 2
    const walkFrame = Math.floor(((elapsed * 60 / 64) % 1) * 8) + 1
    const cell = cells[a * 8 + walkFrame - 1]
    for (let y = 0; y < size; y++) cell.copy(sample, ((Math.floor(a / 4) * size + y) * 384 + a % 4 * size) * 4, y * size * 4, (y + 1) * size * 4)
    sequence.push({attack: a, elapsed, walk_frame: walkFrame})
  }
  await png(sample, 384, 288, path.join(review, 'attack-walk-sequence-4x.png'), 4)
  await fs.writeFile(path.join(review, 'sequence.json'), JSON.stringify(sequence, null, 2) + '\n')
  const metaPath = path.join(dest, 'r2a-combat-20261106.json')
  const metadata = JSON.parse(await fs.readFile(metaPath, 'utf8'))
  metadata.attack_walk = {image, canvas_size: [768, atlasHeight], facing: 'front_right', cell_size: [96, 96],
    scale: 2, reference_height: 64, attack_steps: poses.length, walk_phases: 8, frames}
  await fs.writeFile(metaPath, JSON.stringify(metadata, null, 2) + '\n')
  console.log(JSON.stringify({image: path.join(dest, image), review, frames: frames.length}))
}
async function loadSource() {
  const src = await sharp(path.join(__dirname, 'style-studies/eight-direction-consistency/turnaround-idle-64-v3.png'))
    .extract({left: 80, top: 0, width: 80, height: 80}).ensureAlpha().raw().toBuffer()
  const parts = {upper: cut(src, masks.upper, navy), fore: cut(src, masks.fore),
    hand: cut(src, masks.hand), bat: cut(src, masks.bat)}
  return {src, parts}
}
async function buildR2ap() {
  const {src, parts} = await loadSource()
  const adjustments = require('./r2ap-front-right.json')
  const attackPoses = poses.map(({name, label}, i) => ({name, label, ...adjustments[i]}))
  const body = Buffer.from(src)
  for (let p = 0; p < body.length; p += 4) {
    if (Object.values(parts).some(part => part[p + 3])) body.fill(0, p, p + 4)
  }
  const hit = renderArm(parts, attackPoses[4])
  const cells = attackPoses.map(pose => {
    const frame = Buffer.alloc(size * size * 4)
    if (!pose.elbow) {
      paint(frame, src, (x, y) => [x, y])
      return frame
    }
    const {arm, weapon} = pose === attackPoses[4] ? hit : renderArm(parts, pose)
    const bodyCell = Buffer.alloc(frame.length)
    paint(bodyCell, body, (x, y) => [x, y])
    const torso = shiftWeight(bodyCell, size, offset, pose.weight, 49, 60)
    const layers = pose.behind ? [weapon, arm, torso] : [torso, arm, weapon]
    for (const layer of layers) overlay(frame, layer, size, size)
    return frame
  })
  return {cells, walk: await attackWalk(null, null, parts, attackPoses), times, hit}
}
async function legacyReview() {
  const review = path.join(root, 'output/review/R2-FR12-art')
  const dest = path.join(review, 'legacy')
  await fs.mkdir(dest, {recursive: true}); await fs.mkdir(review, {recursive: true})
  const {src, parts} = await loadSource(), body = Buffer.from(src)
  for (let p = 0; p < body.length; p += 4) if (Object.values(parts).some(b => b[p + 3])) body.fill(0, p, p + 4)
  const atlas = Buffer.alloc(384 * 288 * 4), cells = []
  for (const pose of poses) {
    const b = Buffer.alloc(size * size * 4)
    if (!pose.elbow) paint(b, src, (x, y) => [x, y])
    else {
      const arm = Buffer.alloc(b.length), angle = pose.hand * Math.PI / 180
      const grip = [pose.wrist[0] + Math.cos(angle) - 6 * Math.sin(angle), pose.wrist[1] + Math.sin(angle) + 6 * Math.cos(angle)]
      segment(arm, parts.upper, [27, 32], [27, 40], [27, 32], pose.elbow)
      segment(arm, parts.fore, [27, 40], [28, 46], pose.elbow, pose.wrist)
      rotate(arm, parts.hand, [28, 46], pose.wrist, pose.hand)
      const weapon = Buffer.alloc(b.length); rotate(weapon, parts.bat, [29, 52], grip, pose.bat)
      const layers = pose.behind ? [weapon, arm, null] : [null, arm, weapon]
      for (const layer of layers) {
        if (!layer) paint(b, body, (x, y) => [x, y])
        else for (let p = 0; p < b.length; p += 4) if (layer[p + 3]) layer.copy(b, p, p, p + 4)
      }
      pose.grip = grip
    }
    cells.push(b)
  }
  for (let f = 0; f < poses.length; f++) for (let y = 0; y < size; y++) cells[f].copy(atlas, ((Math.floor(f / 4) * size + y) * 384 + f % 4 * size) * 4, y * size * 4, (y + 1) * size * 4)
  await png(atlas, 384, 288, path.join(dest, 'r2a-attack-front-right-20261106.png'))
  await png(atlas, 384, 288, path.join(review, 'attack-12poses-4x.png'), 4)
  const previousFile = path.join(review, 'previous/r2a-attack-front-right-20261106.png')
  const previous = await fs.readFile(previousFile).catch(error => {if (error.code === 'ENOENT') return null; throw error})
  if (previous) {
    const old = await sharp(previous).ensureAlpha().raw().toBuffer(), comparison = Buffer.alloc(576 * 192 * 4), keyIndices = [0, 2, 4, 6, 8, 11]
    for (let f = 0; f < 6; f++) for (let y = 0; y < size; y++) {
      const from = ((Math.floor(f / 3) * size + y) * 288 + f % 3 * size) * 4
      old.copy(comparison, (y * 576 + f * size) * 4, from, from + 384)
      cells[keyIndices[f]].copy(comparison, ((96 + y) * 576 + f * size) * 4, y * 384, (y + 1) * 384)
    }
    await png(comparison, 576, 192, path.join(review, 'previous-six-vs-new-keys-3x.png'), 3)
  }
  const zombie = Buffer.alloc(240 * 80 * 4), rows = {}
  for (let state = 0; state < 3; state++) {
    const b = Buffer.alloc(80 * 80 * 4)
    const rect = (x, y, w, h, hex) => {const color = [0, 2, 4].map(n => parseInt(hex.slice(n, n + 2), 16)); for (let yy = y; yy < y + h; yy++) for (let xx = x; xx < x + w; xx++) b.set([...color, 255], (yy * 80 + xx) * 4)}
    const skin = state === 1 ? 'bc8060' : '8d9a70', shirt = state === 1 ? '855a47' : '5b6652'
    if (state < 2) {
      rect(31, 10, 20, 18, '15141b'); rect(33, 12, 16, 14, skin); rect(32, 9, 18, 5, '242633')
      rect(35, 17, 3, 3, '15141b'); rect(44, 17, 3, 3, '15141b'); rect(38, 23, 7, 2, '5b3e35')
      rect(27, 28, 27, 24, '15141b'); rect(29, 29, 23, 21, shirt); rect(40, 30, 2, 20, '392b29')
      rect(22, 31, 8, 19, '15141b'); rect(24, 33, 4, 14, shirt); rect(23, 47, 7, 7, '15141b'); rect(25, 48, 4, 4, skin)
      rect(51, 31, 8, 19, '15141b'); rect(53, 33, 4, 14, shirt); rect(51, 47, 7, 7, '15141b'); rect(52, 48, 4, 4, skin)
      rect(29, 51, 11, 16, '15141b'); rect(31, 52, 7, 14, '323648'); rect(42, 51, 11, 16, '15141b'); rect(44, 52, 7, 14, '323648')
      rect(27, 66, 14, 7, '15141b'); rect(29, 67, 10, 4, '5b3e35'); rect(42, 66, 14, 7, '15141b'); rect(44, 67, 10, 4, '5b3e35')
    } else {
      rect(16, 67, 20, 6, '15141b'); rect(18, 68, 17, 3, '323648'); rect(32, 63, 25, 10, '15141b'); rect(34, 65, 21, 6, '5b6652')
      rect(55, 61, 17, 12, '15141b'); rect(57, 63, 13, 8, '8d9a70'); rect(60, 66, 6, 2, '5b3e35'); rect(61, 72, 13, 2, 'a54816')
    }
    if (state === 0) for (let y = 0; y < 80; y++) {
      const runs = []; let start = -1
      for (let x = 0; x <= 80; x++) {const on = x < 80 && b[(y * 80 + x) * 4 + 3]; if (on && start < 0) start = x; if (!on && start >= 0) {runs.push([start, x - 1]); start = -1}}
      if (runs.length) rows[y] = runs
    }
    for (let y = 0; y < 80; y++) b.copy(zombie, (y * 240 + state * 80) * 4, y * 320, (y + 1) * 320)
  }
  await png(zombie, 240, 80, path.join(dest, 'r2a-zombie-20261106.png'))
  await png(zombie, 240, 80, path.join(review, 'zombie-states-4x.png'), 4)
  const metaPath = path.join(dest, 'r2a-combat-20261106.json')
  const metadata = {
    ...JSON.parse(await fs.readFile(metaPath, 'utf8').catch(error => {
      if (error.code === 'ENOENT') return '{}'
      throw error
    })),
    attack: {image: 'r2a-attack-front-right-20261106.png', canvas_size: [384, 288], facing: 'front_right', cell_size: [96, 96], scale: 2, reference_height: 64,
      frames: poses.map((p, i) => ({name: p.name, label: p.label, start: times[i], end: times[i + 1], clip_topleft: [i % 4 * 96, Math.floor(i / 4) * 96, 96, 96], foot_pivot_topleft: [i % 4 * 96 + 48, Math.floor(i / 4) * 96 + 80]}))},
    zombie: {image: 'r2a-zombie-20261106.png', canvas_size: [240, 80], scale: 2, reference_height: 64, opaque_rows: rows,
      frames: Object.fromEntries(['alive', 'stunned', 'dead'].map((name, i) => [name, {clip_topleft: [i * 80, 0, 80, 80], foot_pivot_topleft: [i * 80 + 40, 72]}]))}
  }
  await fs.writeFile(path.join(dest, 'r2a-combat-20261106.json'), JSON.stringify(metadata, null, 2) + '\n')
  await fs.writeFile(path.join(review, 'arm-poses.json'), JSON.stringify({source: 'approved front_right native80', masks, shoulder: [27, 32], poses}, null, 2) + '\n')
  await attackWalk(dest, review, parts)
  console.log(JSON.stringify({attack: path.join(dest, metadata.attack.image), metadata: path.join(dest, 'r2a-combat-20261106.json'), review}))
}
async function main() {
  if (process.argv.includes('--legacy-review')) return legacyReview()
  const result = await buildR2ap()
  const dest = path.join(root, 'game/assets/combat')
  // The stationary atlas is built independently by r2sf-front-right.cjs.
  await png(result.walk.atlas, 8 * size, 12 * size, path.join(dest, 'r2aw-attack-walk-front-right-20261106.png'))
}
if (require.main === module) main().catch(error => {console.error(error); process.exitCode = 1})
module.exports = {buildR2ap}
