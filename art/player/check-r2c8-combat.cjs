// Read-only resource checks; writes only an ignored review report.
const fs = require('node:fs/promises'), path = require('node:path')
const assert = require('node:assert/strict'), {execFileSync} = require('node:child_process'), {createHash} = require('node:crypto')
const sharp = require('sharp'), settings = require('./r2c8-rigs.json')
const walk = require('./consistent-rig.json')
const rigs = {...walk.facings, ...require('./consistent-front-back.json'), ...require('./consistent-side.json'), ...require('./consistent-diagonal.json')}
const root = path.resolve(__dirname, '../..'), baseline = 'c9e017b'
const git = args => execFileSync('git', args, {cwd: root})
const raw = file => sharp(path.join(root, file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
const times = [0, .045, .09, .135, .18, .225, .27, .32, .37, .425, .48, .54, .60]
const names = ['anticipate_1', 'anticipate_mid', 'anticipate_2', 'swing_mid', 'hit', 'hit_follow_mid', 'follow', 'follow_recover_mid', 'recover', 'recover_return_1', 'recover_return_2', 'return']
const oldIndices = [0, 2, 4, 6, 8, 11]
function cell(data, width, index, columns, size = 96) {
  const b = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y++) {
    const start = ((Math.floor(index / columns) * size + y) * width + index % columns * size) * 4
    data.copy(b, y * size * 4, start, start + size * 4)
  }
  return b
}
function padded(b) {
  const out = Buffer.alloc(96 * 96 * 4)
  for (let y = 0; y < 80; y++) b.copy(out, ((y + 8) * 96 + 8) * 4, y * 320, (y + 1) * 320)
  return out
}
function smallComponents(b) {
  const seen = new Uint8Array(96 * 96)
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
  const metaFile = 'game/assets/combat/r2a-combat-20261106.json'
  const metadata = JSON.parse(await fs.readFile(path.join(root, metaFile), 'utf8'))
  const original = JSON.parse(git(['show', `${baseline}:${metaFile}`]).toString())
  // C812 changes only the fourteen C8 sources; completed FR12 and zombie stay exact.
  const preservedKeys = ['attack', 'attack_walk', 'zombie']
  assert.deepEqual(Object.keys(metadata).sort(), Object.keys(original).sort(), 'unchanged source names')
  for (const key of preservedKeys) assert.deepEqual(metadata[key], original[key], `${key} baseline`)
  const frozenPaths = ['game/assets/player', 'art/player/consistent-parts', 'art/player/style-studies/eight-direction-consistency',
    'art/player/consistent-walk.cjs', 'art/player/consistent-rig.json', 'art/player/consistent-front-back.json',
    'art/player/consistent-side.json', 'art/player/consistent-diagonal.json', 'art/player/check-walk-outline.cjs',
    'game/core.py', 'game/locomotion.py', 'game/player_visual.py', 'game/combat.py',
    'art/player/r2a-combat-assets.cjs',
    ...preservedKeys.map(k => `game/assets/combat/${original[k].image}`)]
  assert.equal(git(['diff', '--name-only', baseline, '--', ...frozenPaths]).toString().trim(), '', 'frozen inputs/resources')
  const originalSettings = JSON.parse(git(['show', `${baseline}:art/player/r2c8-rigs.json`]).toString()), retainedSettings = structuredClone(settings)
  for (const model of Object.values(retainedSettings)) {delete model.followRecoverFraction; delete model.returnArcDegrees}
  assert.deepEqual(retainedSettings, originalSettings, 'unchanged source masks and core rig settings')
  const source = await raw('art/player/style-studies/eight-direction-consistency/turnaround-idle-64-v3.png'), palette = new Set()
  for (let p = 0; p < source.data.length; p += 4) if (source.data[p + 3]) palette.add(source.data.subarray(p, p + 3).toString('hex'))
  const report = {baseline, sources: 0, poses: 0, activePoses: 0, smallComponents: 0, exactOldKeys: 0, exactReturns: 0, headPixels: 0, alphaErrors: 0, paletteErrors: 0, edgePixels: 0, sourceCleanupRegressions: 0, gripAnchorChecks: 0, middleBoneChecks: 0, preservedBlocks: preservedKeys.length, frozenPaths: frozenPaths.length, facings: [], unique: {}}
  const snapshots = [[metaFile, await fs.readFile(path.join(root, metaFile))]]
  for (const facing of Object.keys(settings)) {
    const slug = facing.replaceAll('_', '-'), r1 = await raw(`game/assets/player/r1-consistent-${slug}-20261105.png`)
    const [sx, sy] = rigs[facing].sourceCell
    for (const moving of [false, true]) {
      const key = `${moving ? 'attack_walk' : 'attack'}_${facing}`, entry = metadata[key]
      const width = moving ? 768 : 384, height = moving ? 1152 : 288, cols = moving ? 8 : 4
      assert(entry, key); assert.equal(entry.facing, facing); assert.deepEqual(entry.canvas_size, [width, height])
      assert.deepEqual(entry.cell_size, [96, 96]); assert.equal(entry.scale, 2); assert.equal(entry.reference_height, 64)
      assert.equal(entry.image, `r2c8-${moving ? 'attack-walk' : 'attack'}-${slug}-20261106.png`)
      assert.equal(entry.frames.length, moving ? 96 : 12)
      if (moving) {assert.equal(entry.attack_steps, 12); assert.equal(entry.walk_phases, 8)}
      const file = `game/assets/combat/${entry.image}`, image = await raw(file)
      assert.equal(image.info.width, width); assert.equal(image.info.height, height)
      const oldEntry = original[key], oldImage = await sharp(git(['show', `${baseline}:game/assets/combat/${oldEntry.image}`])).ensureAlpha().raw().toBuffer({resolveWithObject: true}), hashes = [], phaseHashes = Array.from({length: 8}, () => new Set())
      snapshots.push([file, await fs.readFile(path.join(root, file))]); report.sources++
      for (let i = 0; i < entry.frames.length; i++) {
        const a = moving ? Math.floor(i / 8) : i, w = moving ? i % 8 : 0, frame = entry.frames[i]
        assert.deepEqual(frame.clip_topleft, [i % cols * 96, Math.floor(i / cols) * 96, 96, 96])
        assert.deepEqual(frame.foot_pivot_topleft, [i % cols * 96 + 48, Math.floor(i / cols) * 96 + 80])
        if (moving) {assert.equal(frame.attack_index, a); assert.equal(frame.walk_frame_index, w + 1)}
        else {assert.equal(frame.name, names[a]); assert.equal(frame.start, times[a]); assert.equal(frame.end, times[a + 1])}
        const b = cell(image.data, width, i, cols), drop = moving ? walk.bodyDrop[w] : 0
        const hash = createHash('sha256').update(b).digest('hex')
        hashes.push(hash); phaseHashes[w].add(hash)
        // Review future tiny components as possible occluded weapon tips; never auto-delete them.
        if (a < 11) {report.activePoses++; report.smallComponents += smallComponents(b)}
        // Source remnants reported in the enlarged SDL review, before any movement.
        if (!moving && i === 0) for (const [x, y] of ({front: [[35, 53], [36, 53], [34, 60]], back_right: [[59, 53]], back_left: [[58, 51]], back: [[64, 76]], front_left: [[37, 48], [36, 52]]}[facing] || [])) {
          assert.equal(b[(y * 96 + x) * 4 + 3], 0, `${key} detached source pixel ${x},${y}`)
          report.sourceCleanupRegressions++
        }
        for (let y = 0; y < 96; y++) for (let x = 0; x < 96; x++) {
          const p = (y * 96 + x) * 4, alpha = b[p + 3]
          if (alpha !== 0 && alpha !== 255) report.alphaErrors++
          if (alpha && !palette.has(b.subarray(p, p + 3).toString('hex'))) report.paletteErrors++
          if (alpha && (x === 0 || y === 0 || x === 95 || y === 95)) report.edgePixels++
        }
        for (let y = 0; y <= 26; y++) for (let x = 0; x < 80; x++) {
          const from = ((sy + y) * source.info.width + sx + x) * 4, to = ((y + 8 + drop) * 96 + x + 8) * 4
          if (source.data[from + 3]) {assert(b.subarray(to, to + 4).equals(source.data.subarray(from, from + 4)), `${key}:${i} head ${x},${y}`); report.headPixels++}
        }
        if (oldIndices.includes(a)) {
          const oldIndex = oldIndices.indexOf(a) * (moving ? 8 : 1) + (moving ? w : 0)
          assert(b.equals(cell(oldImage.data, oldImage.info.width, oldIndex, moving ? 8 : 3)), `${key}:${i} old key RGBA`)
          report.exactOldKeys++
        }
        if (a === 11) {assert(b.equals(padded(cell(r1.data, 320, moving ? w : 8, 4, 80))), `${key}:${i} return RGBA`); report.exactReturns++}
        report.poses++
      }
      assert.equal(new Set(hashes).size, moving ? 96 : 12, `${key} distinct actual poses`)
      if (moving) assert.deepEqual(phaseHashes.map(s => s.size), Array(8).fill(12), `${key} twelve poses per walk phase`)
      report.unique[key] = new Set(hashes).size
    }
    report.facings.push(facing)
  }
  assert.equal(report.alphaErrors, 0); assert.equal(report.paletteErrors, 0); assert.equal(report.edgePixels, 0)
  assert.equal(report.sources, 14); assert.equal(report.poses, 756); assert.equal(report.exactOldKeys, 378); assert.equal(report.exactReturns, 63)
  assert.equal(report.sourceCleanupRegressions, 8)
  assert.equal(report.activePoses, 693); assert.equal(report.smallComponents, 0)
  const poses = JSON.parse(await fs.readFile(path.join(root, 'output/review/R2-C812-art/pose-joints.json'), 'utf8'))
  for (const [facing, sequence] of Object.entries(poses)) {
    assert.equal(sequence.length, 12)
    const model = settings[facing], lengths = p => [Math.hypot(p.elbow[0] - model.shoulder[0], p.elbow[1] - model.shoulder[1]), Math.hypot(p.wrist[0] - p.elbow[0], p.wrist[1] - p.elbow[1])]
    for (const p of sequence.slice(0, 11)) {
      const dx = model.hand.grip[0] - model.hand.anchor[0], dy = model.hand.grip[1] - model.hand.anchor[1], c = Math.cos(p.handAngle), s = Math.sin(p.handAngle)
      assert(Math.hypot(p.grip[0] - p.wrist[0] - c * dx + s * dy, p.grip[1] - p.wrist[1] - s * dx - c * dy) < 1e-8, `${facing} held grip`)
      report.gripAnchorChecks++
    }
    for (const [i, from, to] of [[1, 0, 2], [3, 2, 4], [5, 4, 6], [7, 6, 8], [9, 8, 11], [10, 8, 11]]) {
      const a = lengths(sequence[from]), b = lengths(sequence[to]), middle = lengths(sequence[i])
      for (let bone = 0; bone < 2; bone++) {assert(middle[bone] >= Math.min(a[bone], b[bone]) - 1e-8 && middle[bone] <= Math.max(a[bone], b[bone]) + 1e-8, `${facing}:${i} bone length`); report.middleBoneChecks++}
    }
  }
  const output = execFileSync(process.execPath, ['-e', "require('./art/player/r2c8-combat-assets.cjs')"], {cwd: root})
  assert.equal(output.length, 0, 'require must not bake')
  for (const [file, before] of snapshots) assert(before.equals(await fs.readFile(path.join(root, file))), `${file} import unchanged`)
  report.requireSideEffects = 0
  await fs.writeFile(path.join(root, 'output/review/R2-C812-art/asset-check.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify(report))
}
main().catch(error => {console.error(error); process.exitCode = 1})
