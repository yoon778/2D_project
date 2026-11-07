// Authored full-body stationary poses. The approved idle anchors face, boots, and recovery.
const path = require('node:path')
const sharp = require('sharp')
const poses = require('./r2sf-front-right.json')
const size = 96
const outline = '15141b', shade = '242633', cloth = '323648', facet = '42495f'
const skin = 'e9af89', lightSkin = 'ffcfaa', skinShade = 'bc8060'
const leather = '5b3e35', leatherLight = '855a47', leatherDark = '392b29'
const root = path.resolve(__dirname, '../..')
const atlasPath = path.join(root, 'game/assets/combat/r2a-attack-front-right-20261106.png')

function inside(points, x, y) {
  let inside = false
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [ax, ay] = points[i], [bx, by] = points[j]
    if ((ay > y) !== (by > y) && x < (bx - ax) * (y - ay) / (by - ay) + ax) inside = !inside
  }
  return inside
}
function paint(sprite, color, points) {
  const rgba = Buffer.from(color + 'ff', 'hex')
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    if (inside(points, x + .5, y + .5)) rgba.copy(sprite, (y * size + x) * 4)
  }
}
function local(sprite, color, [x, y], points) {
  paint(sprite, color, points.map(([u, v]) => [u + x, v + y]))
}
function sweep(sprite, color, from, to, profile) {
  const length = Math.hypot(to[0] - from[0], to[1] - from[1])
  const tangent = [(to[0] - from[0]) / length, (to[1] - from[1]) / length]
  const points = profile.map(([along, across]) => [
    from[0] + tangent[0] * along * length - tangent[1] * across,
    from[1] + tangent[1] * along * length + tangent[0] * across,
  ])
  paint(sprite, color, points)
}
function limb(sprite, joints, widths, inner, highlight) {
  for (const inset of [0, 1]) {
    for (let i = 0; i < joints.length - 1; i++) {
      const start = widths[i] - inset, end = widths[i + 1] - inset
      sweep(sprite, inset ? inner : outline, joints[i], joints[i + 1],
        [[-.12, -start * .65], [0, -start], [1, -end], [1.13, -end * .68],
          [1.13, end * .68], [1, end], [0, start], [-.12, start * .65]])
    }
  }
  sweep(sprite, highlight, joints[0], joints[1], [[.11, -1.5], [.22, -2.1], [.79, -1.65], [.64, -.6], [.21, -.15]])
  sweep(sprite, highlight, joints[1], joints[2], [[.18, -.75], [.6, -1.05], [.84, -.7], [.71, .15], [.21, .35]])
}
function boot(sprite, idle, point, far) {
  const [anchorX, anchorY] = far ? [56, 73] : [46, 74]
  const [left, right, top, bottom] = far ? [51, 62, 72, 79] : [42, 51, 74, 80]
  for (let y = top; y <= bottom; y++) for (let x = left; x <= right; x++) {
    const from = (y * size + x) * 4
    const to = ((y + point[1] - anchorY) * size + x + point[0] - anchorX) * 4
    if (idle[from + 3]) idle.copy(sprite, to, from, from + 4)
  }
}
function backpack(sprite, origin) {
  local(sprite, outline, origin, [[-6,0],[-5,-5],[-1,-9],[4,-8],[7,-4],[7,4],[5,12],[1,14],[-5,10],[-7,5]])
  local(sprite, 'a54816', origin, [[-5,-1],[-4,-5],[-1,-8],[3,-7],[5,-4],[5,7],[2,11],[-4,10],[-6,5]])
  local(sprite, 'ef770b', origin, [[-4,-4],[-1,-7],[2,-6],[3,-4],[2,0],[-4,1],[-5,-1]])
  local(sprite, leatherDark, origin, [[-6,3],[-1,2],[3,3],[4,8],[1,12],[-5,9]])
  local(sprite, 'a54816', origin, [[-5,4],[-1,3],[1,4],[0,9],[-3,9],[-5,7]])
  local(sprite, 'ef770b', origin, [[-4,4],[-1,4],[-2,6],[-5,6]])
}
function parcel(sprite, origin) {
  local(sprite, outline, origin, [[-8,-3],[-3,-6],[7,-4],[7,4],[3,7],[-8,5]])
  local(sprite, 'b77c40', origin, [[-7,-2],[2,0],[2,6],[-7,4]])
  local(sprite, '855a47', origin, [[-7,3],[2,5],[2,6],[-7,4]])
  local(sprite, '8a5430', origin, [[2,0],[6,-3],[6,4],[2,6]])
  local(sprite, 'dda65d', origin, [[3,0],[6,-2],[6,2],[3,4]])
  local(sprite, 'f5c687', origin, [[-7,-3],[-3,-5],[6,-4],[2,-1]])
  local(sprite, 'ffe2ac', origin, [[-3,-4],[-1,-5],[4,-3],[2,-2]])
  local(sprite, 'f5c687', origin, [[2,-1],[3,-1],[3,2],[2,3]])
  local(sprite, 'd7a059', origin, [[-5,0],[-3,0],[-2,2],[-4,2],[-5,1]])
}
function fist(sprite, at, carry = false) {
  if (carry) {
    local(sprite, outline, at, [[-5,0],[-3,-2],[0,-3],[2,-4],[4,-2],[4,1],[2,3],[-4,3]])
    local(sprite, skinShade, at, [[-4,0],[-2,-2],[1,-3],[3,-2],[3,0],[1,2],[-3,2]])
    local(sprite, lightSkin, at, [[-3,0],[-1,-1],[1,-3],[3,-2],[2,0],[0,2],[-3,1]])
    return
  }
  local(sprite, outline, at, [[-3,-2],[-1,-4],[2,-3],[4,-1],[3,2],[1,3],[-2,3],[-3,1]])
  local(sprite, skinShade, at, [[-2,-1],[-1,-3],[1,-2],[3,-1],[2,1],[1,2],[-2,2]])
  local(sprite, skin, at, [[-1,-2],[1,-2],[2,-1],[2,0],[1,2],[-2,1],[-2,0]])
  local(sprite, lightSkin, at, [[-1,-2],[1,-1],[1,0],[0,1],[-2,0]])
}
function weapon(sprite, grip, tip) {
  sweep(sprite, outline, grip, tip, [[-.13,-1],[.04,-1.7],[.32,-1.5],[.69,-2.55],[.96,-3.25],[1.04,-1.8],[1.04,1.8],[.94,3],[.63,2.6],[.22,1.5],[-.13,1]])
  sweep(sprite, 'b77c40', grip, tip, [[-.06,-.7],[.29,-.85],[.76,-1.8],[.96,-2.25],[1,.1],[.93,1.9],[.6,1.35],[.11,.75],[-.06,.55]])
  sweep(sprite, 'dda65d', grip, tip, [[.16,-.8],[.72,-1.6],[.94,-1.85],[.97,-.65],[.87,.6],[.58,.85],[.2,.5]])
  sweep(sprite, 'f5c687', grip, tip, [[.56,-.9],[.93,-1.45],[.93,-.2],[.73,.22],[.49,.16]])
  sweep(sprite, 'a96d32', grip, tip, [[.22,.42],[.66,1.05],[.96,.9],[.92,1.4],[.56,1.24],[.21,.8]])
}
function head(sprite, idle, [dx, dy, tilt]) {
  const chin = {30: [42,60],31: [42,59],32: [43,57],33: [45,51],34: [47,56],35: [48,55],36: [50,55],37: [51,54]}
  for (let y = 18; y <= 37; y++) {
    const [left, right] = chin[y] || [41,62]
    const shift = Math.round(tilt * (30 - y) / 12)
    for (let x = left; x <= right; x++) {
      const from = (y * size + x) * 4, to = ((y + dy) * size + x + dx + shift) * 4
      if (idle[from + 3]) idle.copy(sprite, to, from, from + 4)
    }
  }
}
function drawPose(pose, idle) {
  if (pose.rest) {
    const sprite = Buffer.from(idle)
    for (let y = 55; y <= 80; y++) {
      sprite.fill(0, (y * size + 32) * 4, (y * size + 42) * 4)
    }
    weapon(sprite, pose.grip, pose.tip)
    fist(sprite, pose.grip)
    return sprite
  }
  const sprite = Buffer.alloc(size * size * 4)
  const {torso, chest, belt, legs, feet, pack, shoulder, grip, tip, carry} = pose
  if (pose.weaponBehind) weapon(sprite, grip, tip)
  for (const i of [1,0]) {
    limb(sprite, legs[i], i ? [4.5,4,3.5] : [5.5,4.5,4], i ? shade : cloth, i ? cloth : facet)
    boot(sprite, idle, feet[i], i === 1)
  }
  backpack(sprite, pack)
  limb(sprite, pose.left, [4.3,3.9,3], shade, facet)
  paint(sprite, outline, torso)
  paint(sprite, cloth, chest)
  const [a,b,c,d,e,f] = chest
  paint(sprite, facet, [a,b,c,[d[0]-2,d[1]-2],[b[0]-1,c[1]+1], [a[0]+1,a[1]+4]])
  paint(sprite, shade, [[f[0]-1,f[1]-3], [a[0]-3,a[1]+5], [a[0]+1,e[1]-2], e, [f[0]+1,f[1]+2]])
  paint(sprite, outline, belt)
  paint(sprite, leather, belt.map(([x,y], i) => [x + (i < 3 ? 1 : -1), y + (i < 3 ? 1 : -1)]))
  local(sprite, leatherLight, belt[1], [[-2,0],[1,0],[1,2],[-2,2]])
  sweep(sprite, outline, [b[0]-1,b[1]+1], [f[0],f[1]+3], [[0,-2],[1,-2],[1,2],[0,2]])
  sweep(sprite, leatherLight, [b[0]-1,b[1]+1], [f[0],f[1]+3], [[0,-.75],[.88,-.75],[.88,.65],[0,.65]])
  local(sprite, outline, [c[0]-3,c[1]+2], [[-3,-2],[2,-2],[3,0],[1,3],[-3,2]])
  local(sprite, 'ef770b', [c[0]-3,c[1]+2], [[-2,-1],[1,-1],[2,0],[1,2],[-2,1]])
  local(sprite, 'ffe276', [c[0]-3,c[1]+2], [[-1,0],[1,0],[0,1],[-1,1]])
  parcel(sprite, pose.parcel)
  fist(sprite, carry, true)
  limb(sprite, pose.right, [4.8,3.8,2.9], cloth, facet)
  local(sprite, outline, shoulder, [[-4,-2],[-2,-4],[3,-3],[5,-1],[3,2],[-3,2]])
  local(sprite, 'ef770b', shoulder, [[-3,-2],[-2,-3],[2,-2],[3,-1],[2,0],[-3,0]])
  local(sprite, 'a54816', shoulder, [[-3,0],[3,0],[2,1],[-2,1]])
  if (!pose.weaponBehind) weapon(sprite, grip, tip)
  fist(sprite, grip)
  head(sprite, idle, pose.head)
  return sprite
}
function grid(cells, columns) {
  const width = columns * size, height = Math.ceil(cells.length / columns) * size
  const pixels = Buffer.alloc(width * height * 4)
  for (const [index, cell] of cells.entries()) for (let y = 0; y < size; y++) {
    const to = ((Math.floor(index / columns) * size + y) * width + index % columns * size) * 4
    cell.copy(pixels, to, y * size * 4, (y + 1) * size * 4)
  }
  return {pixels, width, height}
}
async function loadIdle() {
  const source = await sharp(path.join(root, 'game/assets/player/r1-consistent-front-right-20261105.png'))
    .extract({left: 0, top: 160, width: 80, height: 80}).ensureAlpha().raw().toBuffer()
  const idle = Buffer.alloc(size * size * 4)
  for (let y = 0; y < 80; y++) {
    source.copy(idle, ((y + 8) * size + 8) * 4, y * 320, (y + 1) * 320)
  }
  return idle
}

function holds(pose, sprite) {
  const bat = Buffer.alloc(sprite.length), hand = Buffer.alloc(sprite.length)
  weapon(bat, pose.grip, pose.tip)
  fist(hand, pose.grip)
  // The same native grip is inside both layers, and a hand pixel survives compositing.
  const [x, y] = pose.grip
  const anchor = (y * size + x) * 4
  const right = Boolean(bat[anchor + 3] && hand[anchor + 3]) &&
    sprite.readUInt32LE(anchor) === hand.readUInt32LE(anchor)
  if (pose.rest) return {right, left: true}

  const box = Buffer.alloc(sprite.length), carry = Buffer.alloc(sprite.length)
  parcel(box, pose.parcel)
  fist(carry, pose.carry, true)
  let left = false
  for (let p = 0; p < box.length; p += 4) {
    if (box[p + 3] && carry[p + 3] && sprite.readUInt32LE(p) === carry.readUInt32LE(p)) {
      left = true
      break
    }
  }
  return {right, left}
}

async function buildFullSwing() {
  const idle = await loadIdle()
  const cells = Object.values(poses).map(pose => drawPose(pose, idle))
  const contacts = Object.values(poses).map((pose, index) => holds(pose, cells[index]))
  cells.push(idle)
  return {cells, contacts, ...grid(cells, 4)}
}

async function main() {
  const {pixels, width, height} = await buildFullSwing()
  await sharp(pixels, {raw: {width, height, channels: 4}}).png().toFile(atlasPath)
}
if (require.main === module) main().catch(error => {console.error(error); process.exitCode = 1})
module.exports = {buildFullSwing}
