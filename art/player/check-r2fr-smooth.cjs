// FR12 image/metadata regression checks; no game or resource writes.
const fs = require('node:fs/promises'), path = require('node:path'), assert = require('node:assert/strict')
const {execFileSync} = require('node:child_process'), {createHash} = require('node:crypto'), sharp = require('sharp')
const root = path.resolve(__dirname, '../..'), baseline = '9f33924', frozenBaseline = 'c9e017b', times = [0, .045, .09, .135, .18, .225, .27, .32, .37, .425, .48, .54, .60]
const names = ['anticipate_1', 'anticipate_mid', 'anticipate_2', 'swing_mid', 'hit', 'hit_follow_mid', 'follow', 'follow_recover_mid', 'recover', 'recover_return_1', 'recover_return_2', 'return']
const walk = require('./consistent-rig.json'), oldIndices = [0, 2, 4, 6, 8, 11]
const git = (file, ref = baseline) => execFileSync('git', ['show', `${ref}:${file}`], {cwd: root})
function cell(data, width, clip) {
  const [left, top, w, h] = clip, b = Buffer.alloc(w * h * 4)
  for (let y = 0; y < h; y++) data.copy(b, y * w * 4, ((top + y) * width + left) * 4, ((top + y) * width + left + w) * 4)
  return b
}
function padded(b) {
  const out = Buffer.alloc(96 * 96 * 4)
  for (let y = 0; y < 80; y++) b.copy(out, ((y + 8) * 96 + 8) * 4, y * 320, (y + 1) * 320)
  return out
}
function smallComponents(b) {
  const seen = new Uint8Array(9216)
  let count = 0
  for (let p = 0; p < seen.length; p++) if (!seen[p] && b[p * 4 + 3]) {
    const queue = [p]
    let length = 0
    seen[p] = 1
    while (queue.length) {
      const n = queue.pop(), x = n % 96, y = Math.floor(n / 96)
      length++
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const xx = x + dx, yy = y + dy, next = yy * 96 + xx
        if (xx >= 0 && xx < 96 && yy >= 0 && yy < 96 && !seen[next] && b[next * 4 + 3]) {seen[next] = 1; queue.push(next)}
      }
    }
    if (length <= 2) count++
  }
  return count
}
async function main() {
  const metaFile = 'game/assets/combat/r2a-combat-20261106.json', metadata = JSON.parse(await fs.readFile(path.join(root, metaFile), 'utf8')), original = JSON.parse(git(metaFile))
  const frozen = JSON.parse(git(metaFile, frozenBaseline))
  assert.deepEqual(Object.keys(metadata).sort(), Object.keys(frozen).sort())
  for (const key of ['attack', 'attack_walk', 'zombie']) {
    assert.deepEqual(metadata[key], frozen[key], `${key} completed FR12 baseline`)
    const file = `game/assets/combat/${frozen[key].image}`
    assert((await fs.readFile(path.join(root, file))).equals(git(file, frozenBaseline)), `${file} frozen PNG bytes`)
  }
  const master = await sharp(path.join(__dirname, walk.master)).ensureAlpha().raw().toBuffer({resolveWithObject: true}), palette = new Set()
  for (let p = 0; p < master.data.length; p += 4) if (master.data[p + 3]) palette.add(master.data.subarray(p, p + 3).toString('hex'))
  const source = cell(master.data, master.info.width, [80, 0, 80, 80]), r1 = await sharp(path.join(root, 'game/assets/player/r1-consistent-front-right-20261105.png')).ensureAlpha().raw().toBuffer()
  const report = {baseline, frozenBaseline, frames: 0, distinctStationary: 0, distinctMoving: 0, distinctByWalkPhase: [], exactOldKeys: 0, exactReturns: 0, headPixels: 0, alphaErrors: 0, paletteErrors: 0, edgePixels: 0, smallComponents: 0, preservedMetadataBlocks: 3, frozenImages: 3, middleBoneChecks: 0}
  for (const moving of [false, true]) {
    const key = moving ? 'attack_walk' : 'attack', entry = metadata[key], width = moving ? 768 : 384, height = moving ? 1152 : 288, columns = moving ? 8 : 4
    assert.equal(entry.image, original[key].image); assert.deepEqual(entry.canvas_size, [width, height]); assert.equal(entry.facing, 'front_right')
    assert.deepEqual(entry.cell_size, [96, 96]); assert.equal(entry.scale, 2); assert.equal(entry.reference_height, 64)
    assert.equal(entry.frames.length, moving ? 96 : 12)
    if (moving) {assert.equal(entry.attack_steps, 12); assert.equal(entry.walk_phases, 8)}
    const current = await sharp(path.join(root, 'game/assets/combat', entry.image)).ensureAlpha().raw().toBuffer({resolveWithObject: true}), old = await sharp(git(`game/assets/combat/${entry.image}`)).ensureAlpha().raw().toBuffer({resolveWithObject: true}), hashes = [], phaseHashes = Array.from({length: 8}, () => new Set())
    assert.equal(current.info.width, width); assert.equal(current.info.height, height)
    for (let i = 0; i < entry.frames.length; i++) {
      const a = moving ? Math.floor(i / 8) : i, w = moving ? i % 8 : 0, frame = entry.frames[i], drop = moving ? walk.bodyDrop[w] : 0
      assert.deepEqual(frame.clip_topleft, [i % columns * 96, Math.floor(i / columns) * 96, 96, 96]); assert.deepEqual(frame.foot_pivot_topleft, [i % columns * 96 + 48, Math.floor(i / columns) * 96 + 80])
      if (moving) {assert.equal(frame.attack_index, a); assert.equal(frame.walk_frame_index, w + 1); assert.equal(frame.name, `${names[a]}_walk${w + 1}`)}
      else {assert.equal(frame.name, names[a]); assert.equal(frame.start, times[a]); assert.equal(frame.end, times[a + 1])}
      const b = cell(current.data, width, frame.clip_topleft), hash = createHash('sha256').update(b).digest('hex')
      hashes.push(hash); phaseHashes[w].add(hash); report.frames++; report.smallComponents += smallComponents(b)
      for (let y = 0; y < 96; y++) for (let x = 0; x < 96; x++) {
        const p = (y * 96 + x) * 4, alpha = b[p + 3]
        if (alpha !== 0 && alpha !== 255) report.alphaErrors++
        if (alpha && !palette.has(b.subarray(p, p + 3).toString('hex'))) report.paletteErrors++
        if (alpha && (x === 0 || y === 0 || x === 95 || y === 95)) report.edgePixels++
      }
      for (let y = 0; y <= 26; y++) for (let x = 0; x < 80; x++) {
        const from = (y * 80 + x) * 4, to = ((y + 8 + drop) * 96 + x + 8) * 4
        if (source[from + 3]) {assert(b.subarray(to, to + 4).equals(source.subarray(from, from + 4)), `${key}:${i} head`); report.headPixels++}
      }
      if (oldIndices.includes(a)) {
        const oldIndex = oldIndices.indexOf(a) * (moving ? 8 : 1) + (moving ? w : 0)
        assert(b.equals(cell(old.data, old.info.width, original[key].frames[oldIndex].clip_topleft)), `${key}:${i} old key`); report.exactOldKeys++
      }
      if (a === 11) {
        const index = moving ? w : 8, native = cell(r1, 320, [index % 4 * 80, Math.floor(index / 4) * 80, 80, 80])
        assert(b.equals(padded(native)), `${key}:${i} R1 return`); report.exactReturns++
      }
    }
    if (moving) {report.distinctMoving = new Set(hashes).size; report.distinctByWalkPhase = phaseHashes.map(s => s.size)}
    else report.distinctStationary = new Set(hashes).size
  }
  const {poses} = JSON.parse(await fs.readFile(path.join(root, 'output/review/R2-FR12-art/arm-poses.json'), 'utf8')), rest = {elbow: [27, 40], wrist: [28, 46]}
  const lengths = p => [Math.hypot(p.elbow[0] - 27, p.elbow[1] - 32), Math.hypot(p.wrist[0] - p.elbow[0], p.wrist[1] - p.elbow[1])]
  for (const [i, from, to] of [[1, poses[0], poses[2]], [3, poses[2], poses[4]], [5, poses[4], poses[6]], [7, poses[6], poses[8]], [9, poses[8], rest], [10, poses[8], rest]]) {
    const a = lengths(from), b = lengths(to), middle = lengths(poses[i])
    for (let bone = 0; bone < 2; bone++) {assert(middle[bone] >= Math.min(a[bone], b[bone]) - 1e-8 && middle[bone] <= Math.max(a[bone], b[bone]) + 1e-8, `middle ${i} projected bone length`); report.middleBoneChecks++}
  }
  assert.equal(report.frames, 108); assert.equal(report.distinctStationary, 12); assert.equal(report.distinctMoving, 96); assert.deepEqual(report.distinctByWalkPhase, Array(8).fill(12))
  assert.equal(report.exactOldKeys, 54); assert.equal(report.exactReturns, 9)
  for (const k of ['alphaErrors', 'paletteErrors', 'edgePixels', 'smallComponents']) assert.equal(report[k], 0, k)
  await fs.writeFile(path.join(root, 'output/review/R2-FR12-art/asset-check.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify(report))
}
main().catch(error => {console.error(error); process.exitCode = 1})
