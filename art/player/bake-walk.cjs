// Offline atlas bake: node art/player/bake-walk.cjs [facing], using sharp 0.35.5.
// The game loads the PNG; this skeleton is an asset-authoring tool only.
const path = require('node:path')
const sharp = require('sharp')
const rigs = require('./walk-rigs.json')

const cellSize = 160
const diagonalStep = 8 / Math.sqrt(2)
const stride = [2, 1, 0, -1, -2, -1.45, 0, 1.45].map(x => x * diagonalStep)
const lift = [0, 0, 0, 0, 0, 5, 8, 4]
const kneeBend = [2, 5, 4, 3, 3, 6, 10, 7]
const bootPitch = [-9, 0, 0, 3, 9, 12, 5, -4]
const bodyDrop = [0, 2, 1, 0, 0, 2, 1, 0]
const bodyShift = [0, -0.7, -0.6, 0, 0, 0.7, 0.6, 0]

async function makeParts(rig) {
  const parts = []
  for (const [name, [left, top, width, height]] of Object.entries(rig.rects)) {
    const source = sharp(path.join(__dirname, rig.parts)).extract({left, top, width, height})
    for (const side of name === 'torso' ? ['body'] : ['right', 'left']) {
      const paint = source.clone()
      if (side !== 'body' && side !== rig.nearLeg) paint.modulate({brightness: 0.78})
      const png = await paint.png().toBuffer()
      const mask = name === 'thigh' ? ' mask="url(#kneeCuff)"'
        : name === 'torso' && rig.torso.hipFade ? ' mask="url(#hipJoin)"' : ''
      const image = `width="${width}" height="${height}" xlink:href="data:image/png;base64,${png.toString('base64')}"`
      if (name === 'torso' && rig.torso.bat) {
        // Rotate only the painted bat around its grip in source-local space.
        const {pivot, polygon, angle, scale = 1} = rig.torso.bat
        const points = polygon.map(point => point.join(',')).join(' ')
        parts.push(`<image id="torsoTexture" ${image}/>`
          + `<mask id="batCut"><rect width="${width}" height="${height}" fill="white"/><polygon points="${points}" fill="black"/></mask>`
          + `<clipPath id="batOnly"><polygon points="${points}"/></clipPath>`
          + `<g id="torsobody"><g${mask}><use xlink:href="#torsoTexture" mask="url(#batCut)"/></g>`
          + `<g transform="translate(${pivot}) rotate(${angle}) scale(${scale}) translate(${-pivot[0]} ${-pivot[1]})"><use xlink:href="#torsoTexture" clip-path="url(#batOnly)"/></g></g>`)
      } else {
        parts.push(`<image id="${name + side}"${mask} ${image}/>`)
      }
    }
  }
  const [, , thighWidth, thighHeight] = rig.rects.thigh
  const cuff = '<linearGradient id="kneeFade" x2="0" y2="1"><stop offset=".75" stop-color="white"/><stop offset=".94" stop-color="black"/></linearGradient>'
    + `<mask id="kneeCuff"><rect width="${thighWidth}" height="${thighHeight}" fill="url(#kneeFade)"/></mask>`
  let hips = ''
  if (rig.torso.hipFade) {
    const [x, y, width, height] = rig.torso.hipFade
    const [, , torsoWidth, torsoHeight] = rig.rects.torso
    // Some torso cutouts include pants below the blend area.
    const lowerMask = rig.torso.hideBelowHipFade
      ? `<rect x="${x}" y="${y + height}" width="${width}" height="${torsoHeight - y - height}" fill="black"/>` : ''
    hips = '<linearGradient id="hipFade" x2="0" y2="1"><stop offset="0" stop-color="white"/><stop offset=".75" stop-color="black"/></linearGradient>'
      + `<mask id="hipJoin"><rect width="${torsoWidth}" height="${torsoHeight}" fill="white"/><rect x="${x}" y="${y}" width="${width}" height="${height}" fill="url(#hipFade)"/>${lowerMask}</mask>`
  }
  return cuff + hips + parts.join('')
}

function use(id, transform) {
  return `<use xlink:href="#${id}" transform="${transform}"/>`
}

// Fit the painted limb axis to two projected joints while keeping its width.
function segment(id, start, end, texture) {
  const dx = end[0] - start[0], dy = end[1] - start[1]
  const sx = texture.end[0] - texture.start[0], sy = texture.end[1] - texture.start[1]
  const angle = Math.atan2(dy, dx) * 180 / Math.PI
  const sourceAngle = Math.atan2(sy, sx) * 180 / Math.PI
  const lengthScale = Math.hypot(dx, dy) / Math.hypot(sx, sy)
  return use(id, `translate(${start}) rotate(${angle}) scale(${lengthScale} ${texture.width}) rotate(${-sourceAngle}) translate(${-texture.start[0]} ${-texture.start[1]})`)
}

function drawLeg(rig, side, frame) {
  const idle = frame === 8
  const phase = (frame + (side === 'right' ? 0 : 4)) % 8
  const shift = idle ? 0 : bodyShift[frame] * rig.ground[0]
  const drop = idle ? 0 : bodyDrop[frame]
  const travel = idle ? 0 : stride[phase]
  const raised = idle ? 0 : lift[phase]
  const bend = idle ? 2 : kneeBend[phase]
  const hip = [rig[side].hip[0] + shift, rig[side].hip[1] + drop]
  const ankle = [rig[side].ankle[0] + rig.ground[0] * travel,
    rig[side].ankle[1] + rig.ground[1] * travel - raised]
  const knee = [
    hip[0] + (ankle[0] - hip[0]) * 0.52 + rig.ground[0] * bend,
    hip[1] + (ankle[1] - hip[1]) * 0.50 - bend * 0.24,
  ]
  const pitch = idle ? 0 : bootPitch[phase] * rig.ground[0]
  const boot = use('boot' + side, `translate(${ankle}) rotate(${pitch}) scale(${rig.boot.scale}) translate(${-rig.boot.anchor[0]} ${-rig.boot.anchor[1]})`)
  return boot + segment('shin' + side, knee, ankle, rig.shin)
    + segment('thigh' + side, hip, knee, rig.thigh)
}

async function bake(facing) {
  const rig = rigs[facing]
  if (!rig) throw new Error(`Unknown facing: ${facing}`)
  const parts = await makeParts(rig)
  const poses = []
  const farLeg = rig.nearLeg === 'right' ? 'left' : 'right'
  for (let frame = 0; frame < 9; frame++) {
    const shift = frame === 8 ? 0 : bodyShift[frame] * rig.ground[0]
    const drop = frame === 8 ? 0 : bodyDrop[frame]
    const torso = use('torsobody', `translate(${rig.torso.position[0] + shift} ${rig.torso.position[1] + drop}) scale(${rig.torso.scale})`)
    const x = (frame % 4) * cellSize, y = Math.floor(frame / 4) * cellSize
    poses.push(`<g transform="translate(${x} ${y})">${drawLeg(rig, farLeg, frame)}${drawLeg(rig, rig.nearLeg, frame)}${torso}</g>`)
  }
  const scene = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="640" height="480"><defs>${parts}</defs>${poses.join('')}</svg>`
  const output = path.join(__dirname, `../../game/assets/player/r1-unified-${facing.replaceAll('_', '-')}-20261105.png`)
  await sharp(Buffer.from(scene)).png().toFile(output)
  console.log(`${facing}: ${output}`)
}

async function main() {
  const facings = process.argv[2] ? [process.argv[2]] : Object.keys(rigs)
  for (const facing of facings) await bake(facing)
}
main().catch(error => { console.error(error); process.exitCode = 1 })
