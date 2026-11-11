// Paint character-specific materials onto the approved directional motion atlases.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const rig = require('./r2z-rig.json')
const attackRig = require('./r2za-rigs.json')
const {build: buildAttack} = require('./r2za-zombie-attack.cjs')
const {facings, size} = require('./raster.cjs')
const {bodyDrop} = require('../player/consistent-rig.json')

const root = path.resolve(__dirname, '../..')
const assets = path.join(root, 'game/assets/zombie')
const review = path.join(root, 'output/review/zombie-variants')
const atlases = {
  base: 'r2z-zombie-20261106.png',
  attack: 'r2za-zombie-attack-20261106.png',
}

const cloth = ['757660', '70735d', '6b6e59', '58594a', '645e4f', '504c42', '60463a', '644a3d']
const trousers = ['312f3a', '353139', '2b282b']
const boots = ['644a3d', '60463a', '4e4038']
const rgb = hex => Buffer.from(hex, 'hex')
const palette = (...shades) => shades.map(rgb)
const materials = {
  maintenance: {
    vest: palette('ac8c4e', '9b7d44', '8c6e3d', '6e5634', '705639', '51432f', '624b38', '73563a'),
    sleeve: palette('69777f', '5c6974', '53616d', '3e4957', '48515b', '333944', '4b4143', '594b4c'),
    stripe: palette('d1c29b', 'b6a784', 'a3997d', '8d8167'),
    pants: palette('3d4141', '505252', '343635'),
    boot: palette('584b3e', '4d4338', '403931'),
  },
  resident: {
    cardigan: palette('8a4b56', '7c434e', '713d49', '5b323e', '603743', '492e37', '614047', '67434b'),
    hair: palette('49414c', '38333f', '2b2834'),
    pants: palette('625950', '71665c', '514943'),
    boot: palette('49404a', '3c3540', '302b34'),
  },
}

// Coordinates are measured in the approved 80px idle cells, facing order from raster.cjs.
const vestBounds = [[32, 49], [34, 49], [31, 42], [30, 44], [32, 49], [37, 50], [39, 50], [32, 47]]
const zipperX = [40, 44, null, null, null, null, null, 36]
const directions = [0, 1, 1, 1, 0, -1, -1, -1]

function readCell(atlas, col, row) {
  const cell = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y++) {
    const start = ((row * size + y) * atlas.width + col * size) * 4
    atlas.data.copy(cell, y * size * 4, start, start + size * 4)
  }
  return cell
}

function writeCell(atlas, cell, col, row) {
  for (let y = 0; y < size; y++) {
    const start = y * size * 4
    cell.copy(atlas.data, ((row * size + y) * atlas.width + col * size) * 4, start, start + size * 4)
  }
}

const pixel = (x, y) => (y * size + x) * 4
const color = (cell, at) => cell.subarray(at, at + 3).toString('hex')
const asInfo = (data, width, height) => ({data, width, height})
const encode = ({data, width, height}) => sharp(data, {raw: {width, height, channels: 4}})

async function decode(file) {
  const {data, info} = await sharp(file).ensureAlpha().raw().toBuffer({resolveWithObject: true})
  return asInfo(data, info.width, info.height)
}

function headBounds(cell) {
  let left = size, right = 0, top = size
  for (let y = 0; y < size && y <= top + 13; y++) {
    for (let x = 0; x < size; x++) {
      if (!cell[pixel(x, y) + 3]) continue
      top = Math.min(top, y)
      left = Math.min(left, x)
      right = Math.max(right, x)
    }
  }
  return {center: (left + right) / 2, top}
}

function undoRotation(x, y, pivot, target, degrees) {
  const a = degrees * Math.PI / 180
  const dx = x - target[0], dy = y - target[1]
  return [pivot[0] + Math.cos(a) * dx + Math.sin(a) * dy,
    pivot[1] - Math.sin(a) * dx + Math.cos(a) * dy]
}

function restCoordinates(x, y, col, row, kind, headOffset, attack) {
  const facing = facings[col]
  const model = rig.facings[facing]
  if (kind === 'attack') {
    if (row === 11) return [x, y]
    const [dx, dy] = attack.weights[row]
    const stop = attackRig[facing].protectFromY
    const taper = Math.max(0, Math.min(1, (stop - y) / (stop - 43)))
    return [x - Math.round(dx * taper), y - Math.round(dy * taper)]
  }
  if (row === 13) return undoRotation(x, y, [39, 46], [35, 57], 90)
  if (row >= 9 && row <= 11 && y < 66) {
    const [dx, dy] = model.worldFacing
    const recoil = -[1.5, 3, 1][row - 9] / Math.hypot(dx, dy)
    const pivot = [(model.legs.right.hip[0] + model.legs.left.hip[0]) / 2, model.hipY]
    const target = [pivot[0] + dx * recoil, pivot[1] + dy * .6 * recoil]
    return undoRotation(x, y, pivot, target, -Math.sign(dx || 1) * [2, 5, 1][row - 9])
  }
  if (row >= 14) {
    const phase = Math.floor((row - 14) / 2)
    const progress = ((row - 14) % 2 + 1) / 3
    return [x, Math.round(y - bodyDrop[phase] * progress)]
  }
  if (row >= 1 && row <= 8) {
    return col === 1 ? [x - headOffset[0], y - headOffset[1]] : [x, y - bodyDrop[row - 1]]
  }
  return [x, y]
}

function nearCloth(cell, x, y) {
  return [[-1, 0], [1, 0], [0, -1], [0, 1]].some(([dx, dy]) => {
    const at = pixel(x + dx, y + dy)
    return cell[at + 3] && cloth.slice(0, 4).includes(color(cell, at))
  })
}

function workerCloth(col, x, y, shade, arm) {
  const paint = materials.maintenance
  const [left, right] = vestBounds[col]
  if (x < left || x > right || arm) return paint.sleeve[shade]
  const line = 35 + (x - (left + right) / 2) * .11 * directions[col]
  if (y >= line && y < line + 2.5) return paint.stripe[Math.min(shade, 3)]
  return paint.vest[shade]
}

function residentHair(col, x, y, hex, center) {
  if (y < 10 || y > 29 || hex === rig.outline || hex === '151316') return null
  const side = directions[col]
  const fromCenter = x - center
  const back = col >= 3 && col <= 5
  if (col === 0 && y >= 19 && fromCenter >= -5 && fromCenter <= 7) return null
  const crown = y <= 16 || (y <= 18 && Math.abs(fromCenter) <= 8)
  const fringe = side ? fromCenter * side < (21 - y) * .7 : fromCenter < (19 - y) * .8
  const nape = back ? y <= 25 : fringe && y <= (side ? 27 : 24)
  if (!(crown || nape) || Math.abs(fromCenter) > 11) return null
  if (y > 24 && !cloth.includes(hex) && !rig.trousers.includes(hex)) return null
  const streak = y + fromCenter * (side || 1) * .4
  return materials.resident.hair[streak < 15 ? 0 : streak < 20 ? 1 : 2]
}

function isArmPixel(attack, row, at, cell) {
  return Boolean(attack?.layers[row] && Object.values(attack.layers[row]).some(layer =>
    layer[at + 3] && layer[at] === cell[at] && layer[at + 1] === cell[at + 1] && layer[at + 2] === cell[at + 2]))
}

function paintCell(cell, idle, name, col, row, kind, attack) {
  const out = Buffer.from(cell)
  const head = headBounds(idle)
  const posedHead = headBounds(cell)
  const headOffset = [Math.round(posedHead.center - head.center), posedHead.top - head.top]
  const bodyBottom = rig.facings[facings[col]].hipY + 2
  const paint = materials[name]
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const at = pixel(x, y)
    if (!cell[at + 3]) continue
    const hex = color(cell, at)
    const [restX, restY] = restCoordinates(x, y, col, row, kind, headOffset, attack)
    const shade = cloth.indexOf(hex)
    const arm = kind === 'attack' && shade >= 0 && isArmPixel(attack, row, at, cell)
    const garment = shade >= 0 && (arm || (restY >= 23 && restY <= bodyBottom &&
      (shade < 4 || nearCloth(cell, x, y))))
    let material = name === 'resident' ? residentHair(col, restX, restY, hex, head.center) : null
    if (!material && garment) {
      if (name === 'maintenance') material = workerCloth(col, restX, restY, shade, arm)
      else {
        const zipper = zipperX[col]
        material = zipper !== null && Math.abs(restX - zipper) < .6 && restY >= 32 && !arm
          ? paint.cardigan[5] : paint.cardigan[shade]
      }
    }
    if (!material && (kind === 'base' && row === 13 ? restY > bodyBottom : y >= 45)) {
      const pantsShade = trousers.indexOf(hex), bootShade = boots.indexOf(hex)
      if (pantsShade >= 0) material = paint.pants[pantsShade]
      else if (bootShade >= 0) material = paint.boot[bootShade]
    }
    if (material) material.copy(out, at)
  }
  return out
}

function verifyAlpha(original, variant) {
  assert.deepEqual([variant.width, variant.height], [original.width, original.height])
  for (let i = 3; i < original.data.length; i += 4) assert.equal(variant.data[i], original.data[i])
}

async function preview(file, rows, scale) {
  const output = asInfo(Buffer.alloc(facings.length * rows.length * size * size * 4),
    facings.length * size, rows.length * size)
  for (const [index, [atlas, row]] of rows.entries()) {
    for (const col of facings.keys()) writeCell(output, readCell(atlas, col, row), col, index)
  }
  await encode(output).flatten({background: '#36434b'})
    .resize(Math.round(output.width * scale), Math.round(output.height * scale), {kernel: 'nearest'})
    .png().toFile(path.join(review, file))
}

async function main() {
  const original = Object.fromEntries(await Promise.all(Object.entries(atlases).map(async ([kind, file]) =>
    [kind, await decode(path.join(assets, file))])))
  const attacks = await Promise.all(facings.map(facing => buildAttack(facing)))
  const idle = facings.map((_, col) => readCell(original.base, col, 0))
  const variants = {}
  await fs.mkdir(review, {recursive: true})
  for (const name of Object.keys(materials)) {
    const painted = {}
    for (const [kind, atlas] of Object.entries(original)) {
      const target = asInfo(Buffer.alloc(atlas.data.length), atlas.width, atlas.height)
      let changed = 0
      for (let row = 0; row < atlas.height / size; row++) for (const col of facings.keys()) {
        const source = readCell(atlas, col, row)
        const facing = kind === 'base' && row === 13 ? 1 : col
        const cell = paintCell(source, idle[facing], name, facing, row, kind, attacks[facing])
        if (!cell.equals(source)) changed++
        writeCell(target, cell, col, row)
      }
      assert.equal(changed, kind === 'base' ? 233 : 96)
      const file = path.join(assets, `${name}-${kind}.png`)
      await encode(target).png().toFile(file)
      painted[kind] = await decode(file)
      verifyAlpha(atlas, painted[kind])
    }
    for (const col of facings.keys()) {
      const pose = readCell(painted.base, col, 0)
      assert.deepEqual(readCell(painted.base, col, 12), pose)
      assert.deepEqual(readCell(painted.attack, col, 11), pose)
    }
    variants[name] = painted
    const rows = [0, 1, 4, 8, 9, 10, 12, 13, 14, 15].map(row => [painted.base, row])
      .concat([0, 3, 6, 8, 11].map(row => [painted.attack, row]))
    await preview(`${name}-motion.png`, rows, 1.2)
  }
  await preview('idle-at-game-scale.png', [original.base, variants.maintenance.base, variants.resident.base]
    .map(atlas => [atlas, 0]), 1.2)
  console.log('Verified 2 zombie appearances: 233 base + 96 attack poses each, exact alpha and idle recovery.')
}

main().catch(error => { console.error(error); process.exitCode = 1 })
