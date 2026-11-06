// Read-only resource checks; writes only an ignored review report.
const fs = require('node:fs/promises'), path = require('node:path')
const assert = require('node:assert/strict'), {execFileSync} = require('node:child_process')
const sharp = require('sharp'), settings = require('./r2c8-rigs.json')
const walk = require('./consistent-rig.json')
const rigs = {...walk.facings, ...require('./consistent-front-back.json'), ...require('./consistent-side.json'), ...require('./consistent-diagonal.json')}
const root = path.resolve(__dirname, '../..'), baseline = 'e23de0c'
const git = args => execFileSync('git', args, {cwd: root})
const raw = file => sharp(path.join(root, file)).ensureAlpha().raw().toBuffer({resolveWithObject: true})
const times = [0, .09, .18, .27, .37, .48, .60]
const names = ['anticipate_1', 'anticipate_2', 'hit', 'follow', 'recover', 'return']
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
async function main() {
  const metaFile = 'game/assets/combat/r2a-combat-20261106.json'
  const metadata = JSON.parse(await fs.readFile(path.join(root, metaFile), 'utf8'))
  const original = JSON.parse(git(['show', `${baseline}:${metaFile}`]).toString())
  for (const key of ['attack', 'attack_walk', 'zombie']) assert.deepEqual(metadata[key], original[key], `${key} baseline`)
  const frozenPaths = ['game/assets/player', 'art/player/consistent-parts', 'art/player/style-studies/eight-direction-consistency',
    'art/player/consistent-walk.cjs', 'art/player/consistent-rig.json', 'art/player/consistent-front-back.json',
    'art/player/consistent-side.json', 'art/player/consistent-diagonal.json', 'art/player/check-walk-outline.cjs',
    'game/core.py', 'game/locomotion.py', 'game/player_visual.py', 'game/combat.py',
    ...['attack', 'attack_walk', 'zombie'].map(k => `game/assets/combat/${original[k].image}`)]
  assert.equal(git(['diff', '--name-only', baseline, '--', ...frozenPaths]).toString().trim(), '', 'frozen inputs/resources')
  const source = await raw('art/player/style-studies/eight-direction-consistency/turnaround-idle-64-v3.png'), palette = new Set()
  for (let p = 0; p < source.data.length; p += 4) if (source.data[p + 3]) palette.add(source.data.subarray(p, p + 3).toString('hex'))
  const report = {baseline, sources: 0, poses: 0, exactReturns: 0, headPixels: 0, alphaErrors: 0, paletteErrors: 0, edgePixels: 0, sourceCleanupRegressions: 0, legacyBlocks: 3, frozenPaths: frozenPaths.length, facings: []}
  const snapshots = [[metaFile, await fs.readFile(path.join(root, metaFile))]]
  for (const facing of Object.keys(settings)) {
    const slug = facing.replaceAll('_', '-'), r1 = await raw(`game/assets/player/r1-consistent-${slug}-20261105.png`)
    const [sx, sy] = rigs[facing].sourceCell
    for (const moving of [false, true]) {
      const key = `${moving ? 'attack_walk' : 'attack'}_${facing}`, entry = metadata[key]
      const width = moving ? 768 : 288, height = moving ? 576 : 192, cols = moving ? 8 : 3
      assert(entry, key); assert.equal(entry.facing, facing); assert.deepEqual(entry.canvas_size, [width, height])
      assert.deepEqual(entry.cell_size, [96, 96]); assert.equal(entry.scale, 2); assert.equal(entry.reference_height, 64)
      assert.equal(entry.image, `r2c8-${moving ? 'attack-walk' : 'attack'}-${slug}-20261106.png`)
      assert.equal(entry.frames.length, moving ? 48 : 6)
      const file = `game/assets/combat/${entry.image}`, image = await raw(file)
      assert.equal(image.info.width, width); assert.equal(image.info.height, height)
      snapshots.push([file, await fs.readFile(path.join(root, file))]); report.sources++
      for (let i = 0; i < entry.frames.length; i++) {
        const a = moving ? Math.floor(i / 8) : i, w = moving ? i % 8 : 0, frame = entry.frames[i]
        assert.deepEqual(frame.clip_topleft, [i % cols * 96, Math.floor(i / cols) * 96, 96, 96])
        assert.deepEqual(frame.foot_pivot_topleft, [i % cols * 96 + 48, Math.floor(i / cols) * 96 + 80])
        if (moving) {assert.equal(frame.attack_index, a); assert.equal(frame.walk_frame_index, w + 1)}
        else {assert.equal(frame.name, names[a]); assert.equal(frame.start, times[a]); assert.equal(frame.end, times[a + 1])}
        const b = cell(image.data, width, i, cols), drop = moving ? walk.bodyDrop[w] : 0
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
        if (a === 5) {assert(b.equals(padded(cell(r1.data, 320, moving ? w : 8, 4, 80))), `${key}:${i} return RGBA`); report.exactReturns++}
        report.poses++
      }
    }
    report.facings.push(facing)
  }
  assert.equal(report.alphaErrors, 0); assert.equal(report.paletteErrors, 0); assert.equal(report.edgePixels, 0)
  assert.equal(report.sources, 14); assert.equal(report.poses, 378); assert.equal(report.exactReturns, 63)
  assert.equal(report.sourceCleanupRegressions, 8)
  const output = execFileSync(process.execPath, ['-e', "require('./art/player/r2c8-combat-assets.cjs')"], {cwd: root})
  assert.equal(output.length, 0, 'require must not bake')
  for (const [file, before] of snapshots) assert(before.equals(await fs.readFile(path.join(root, file))), `${file} import unchanged`)
  report.requireSideEffects = 0
  await fs.writeFile(path.join(root, 'output/review/R2-C8-art/asset-check.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify(report))
}
main().catch(error => {console.error(error); process.exitCode = 1})
