// Offline atlas bake: run "node bake-walk.cjs" with sharp 0.35.5 installed.
// The game loads only the resulting PNG and does not run a skeleton at runtime.
const path = require('node:path')
const sharp = require('sharp')

const partsFile = path.join(__dirname, 'courier-walk-parts.png')
const outputFile = path.join(__dirname, '../../game/assets/player/r1-alternating-front-right-20261105.png')
const rects = {
  torso: [141, 40, 398, 569],
  thigh: [847, 146, 204, 367],
  shin: [250, 746, 147, 329],
  boot: [836, 824, 199, 207],
}
const cell = 160
// Distances along the ground at a diagonal. The planted foot moves back
// 8 ground pixels per pose as the character advances by the same distance.
const diagonalStep = 8 / Math.sqrt(2)
const stride = [2, 1, 0, -1, -2, -1.45, 0, 1.45].map(x => x * diagonalStep)
const lift = [0, 0, 0, 0, 0, 5, 8, 4]
const kneeBend = [2, 5, 4, 3, 3, 6, 10, 7]
const bootPitch = [-9, 0, 0, 3, 9, 12, 5, -4]
const bodyDrop = [0, 2, 1, 0, 0, 2, 1, 0]
const bodyShift = [0, -0.7, -0.6, 0, 0, 0.7, 0.6, 0]

async function makeParts() {
  const parts = {}
  for (const [name, [left, top, width, height]] of Object.entries(rects)) {
    const source = sharp(partsFile).extract({left, top, width, height})
    for (const side of name === 'torso' ? ['body'] : ['near', 'far']) {
      const paint = source.clone()
      if (side === 'far') paint.modulate({brightness: 0.78})
      const png = await paint.png().toBuffer()
      const joint = name === 'thigh' ? ' mask="url(#kneeCuff)"'
        : name === 'torso' ? ' mask="url(#hipJoin)"' : ''
      parts[name + side] = `<image id="${name + side}"${joint} width="${width}" height="${height}" xlink:href="data:image/png;base64,${png.toString('base64')}"/>`
    }
  }
  // Blend the trouser leg over the shin where the two painted pieces meet.
  const cuff = '<linearGradient id="kneeFade" x2="0" y2="1"><stop offset=".75" stop-color="white"/><stop offset=".94" stop-color="black"/></linearGradient>'
    + '<mask id="kneeCuff"><rect width="204" height="367" fill="url(#kneeFade)"/></mask>'
  const hips = '<linearGradient id="hipFade" x2="0" y2="1"><stop offset="0" stop-color="white"/><stop offset=".75" stop-color="black"/></linearGradient>'
    + '<mask id="hipJoin"><rect width="398" height="569" fill="white"/><rect x="110" y="357" width="170" height="60" fill="url(#hipFade)"/></mask>'
  return cuff + hips + Object.values(parts).join('')
}

function use(id, transform) {
  return `<use xlink:href="#${id}" transform="${transform}"/>`
}

// Fit the longitudinal axis of each painted part between its two joints.
// Its width stays constant as the projected length changes in the 3/4 view.
function segment(id, start, end, sourceStart, sourceEnd, widthScale) {
  const [dx, dy] = [end[0] - start[0], end[1] - start[1]]
  const [sx, sy] = [sourceEnd[0] - sourceStart[0], sourceEnd[1] - sourceStart[1]]
  const angle = (Math.atan2(dy, dx) - Math.atan2(sy, sx)) * 180 / Math.PI
  const sourceAngle = Math.atan2(sy, sx) * 180 / Math.PI
  const lengthScale = Math.hypot(dx, dy) / Math.hypot(sx, sy)
  return use(id, `translate(${start}) rotate(${angle + sourceAngle}) scale(${lengthScale} ${widthScale}) rotate(${-sourceAngle}) translate(${-sourceStart[0]} ${-sourceStart[1]})`)
}

function drawLeg(side, frame) {
  const near = side === 'near' // Courier's right (bat) side, closer to camera
  const phase = (frame + (near ? 0 : 4)) % 8
  const hip = [(near ? 74 : 86) + bodyShift[frame], (near ? 92 : 90) + bodyDrop[frame]]
  // main.world_to_screen projects world Y at 60% of world X.
  const ankle = [(near ? 76 : 85) + stride[phase],
    (near ? 133 : 128) + 0.60 * stride[phase] - lift[phase]]
  const knee = [
    hip[0] + (ankle[0] - hip[0]) * 0.52 + kneeBend[phase],
    hip[1] + (ankle[1] - hip[1]) * 0.50 - kneeBend[phase] * 0.24,
  ]
  const boot = use('boot' + side, `translate(${ankle}) rotate(${bootPitch[phase]}) scale(0.122 0.092) translate(-68 -54)`)
  const shin = segment('shin' + side, knee, ankle, [77, 39], [64, 280], 0.145)
  const thigh = segment('thigh' + side, hip, knee, [86, 53], [128, 304], 0.140)
  return boot + shin + thigh
}

async function bake() {
  const parts = await makeParts()
  const poses = []
  for (let frame = 0; frame < 8; frame++) {
    // The lamp and head follow the loaded hip, with a subtle dip on 2 and 6.
    // Compensate for the four-pixel crop expansion above the cap.
    const torso = use('torsobody', `translate(${37.5 + bodyShift[frame]} ${20 - 4 * 0.208 + bodyDrop[frame]}) scale(0.208)`)
    const x = (frame % 4) * cell
    const y = Math.floor(frame / 4) * cell
    poses.push(`<g transform="translate(${x} ${y})">${drawLeg('far', frame)}${drawLeg('near', frame)}${torso}</g>`)
  }
  const scene = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="640" height="320"><defs>${parts}</defs>${poses.join('')}</svg>`
  await sharp(Buffer.from(scene)).png().toFile(outputFile)
}
bake().catch(error => { console.error(error); process.exitCode = 1 })
