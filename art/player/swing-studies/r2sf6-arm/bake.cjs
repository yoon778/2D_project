const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require('sharp')
const source = require('./pose-source.json')
const {buildStationaryCells} = require('../../r2sf-front-right.cjs')

const root = path.resolve(__dirname, '../../../..')
const review = path.join(root, 'output/review/R2-SF6-ARM-art')
const output = path.join(__dirname, 'poses.png')
const cellSize = 96
const starts = [0, 30, 180, 240, 300, 440, 660]
const delays = starts.slice(1).map((end, index) => end - starts[index])
const names = ['Idle', 'Load', 'Rotate', 'Hit', 'Follow', 'Recover']
const armColors = ['#62d6e5', '#f8b957', '#b7e284', '#f28eaf']
const armNames = ['Shoulder', 'Elbow', 'Wrist', 'Grip']
const idleArm = [[41,40], [40,48], [38,55], [38,58]]
const raw = (pixels, width, height, extra = {}) => sharp(pixels, {raw: {width,height,channels:4,...extra}})
const colorSet = cell => new Set(Array.from({length: cell.length / 4}, (_, i) => cell.readUInt32BE(i * 4)))

function connected(cell) {
  const unseen = new Set()
  for (let i = 0; i < cellSize * cellSize; i++) if (cell[i * 4 + 3]) unseen.add(i)
  assert(unseen.size)
  const first = unseen.values().next().value
  const queue = [first]
  unseen.delete(first)
  for (const p of queue) {
    const x = p % cellSize, y = Math.floor(p / cellSize)
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (x + dx < 0 || x + dx >= cellSize || y + dy < 0 || y + dy >= cellSize) continue
      const next = (y + dy) * cellSize + x + dx
      if (unseen.delete(next)) queue.push(next)
    }
  }
  return unseen.size === 0
}

function frameEdges(cell) {
  for (let i = 0; i < cellSize; i++) {
    for (const p of [i, (cellSize - 1) * cellSize + i, i * cellSize, (i + 1) * cellSize - 1]) {
      assert.equal(cell[p * 4 + 3], 0)
    }
  }
}

function drawJoints(arms, scale, width, height) {
  const header = 28
  const groups = arms.map((arm, i) => {
    const points = arm.map(([x, y]) => [(i * cellSize + x + .5) * scale, header + (y + .5) * scale])
    const chain = points.map(p => p.join(',')).join(' ')
    const nodes = points.map(([x, y], j) =>
      '<circle cx="'+x+'" cy="'+y+'" r="5.5" fill="'+armColors[j]+'" stroke="#111820" stroke-width="1.8"/>').join('')
    return '<g><text x="'+(i*cellSize*scale+10)+'" y="19">'+i+' '+names[i]+' · '+starts[i]+' ms</text>'+
      '<polyline points="'+chain+'" fill="none" stroke="#101921" stroke-width="6" stroke-linejoin="round"/>'+
      '<polyline points="'+chain+'" fill="none" stroke="#edf6f8" stroke-width="2.2" stroke-linejoin="round"/>'+nodes+'</g>'
  }).join('')
  const legend = armNames.map((name, i) =>
    '<circle cx="'+(20+i*135)+'" cy="'+(height-18)+'" r="5" fill="'+armColors[i]+'"/>'+
    '<text x="'+(33+i*135)+'" y="'+(height-13)+'">'+name+'</text>').join('')
  return Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="'+width+'" height="'+height+'">'+
    '<g font-family="sans-serif" font-size="14" fill="#edf6f8">'+groups+legend+'</g></svg>')
}

async function main() {
  const {cells, contacts, pixels, width, height} = await buildStationaryCells([null, ...source], 6)
  assert.deepEqual([width, height, cells.length], [576, 96, 6])
  assert.equal(contacts.length, 5)
  assert(contacts.every(({left, right}) => left && right), 'parcel and bat contact')
  assert.equal(new Set(cells.map(cell => cell.toString('base64'))).size, 6)
  const approved = colorSet(cells[0])
  const arms = [idleArm, ...source.map(pose => [...pose.right, pose.grip])]
  for (const [index, cell] of cells.entries()) {
    assert(connected(cell), 'disconnected pixels in pose ' + index)
    frameEdges(cell)
    assert([...colorSet(cell)].every(color => approved.has(color)), 'approved palette and binary alpha')
    for (const [row, left, right] of [[80,42,51], [79,52,62]]) {
      const start = (row * cellSize + left) * 4, end = (row * cellSize + right + 1) * 4
      assert(cell.subarray(start,end).equals(cells[0].subarray(start,end)), 'planted sole')
    }
    const arm = arms[index]
    for (const [x, y] of arm) assert(cell[(y * cellSize + x) * 4 + 3], 'joint is inside the sprite')
    const [wx,wy] = arm[2], [gx,gy] = arm[3]
    assert(Math.hypot(wx - gx, wy - gy) <= 4, 'grip is adjacent to wrist')
    if (index) assert.deepEqual(source[index - 1].shoulder, arm[0])
  }

  const png = await raw(pixels,width,height).png().toBuffer()
  await fs.mkdir(review,{recursive:true})
  if (process.argv.includes('--check')) {
    const actual = await sharp(output).ensureAlpha().raw().toBuffer({resolveWithObject:true})
    assert.deepEqual([actual.info.width, actual.info.height], [width,height])
    assert(actual.data.equals(pixels), 'reproducible sheet')
  } else {
    await fs.writeFile(output,png)
  }

  const scale = 3, diagramWidth = width * scale, diagramHeight = height * scale + 64
  const sprite = await raw(pixels,width,height).resize(diagramWidth,height*scale,{kernel:'nearest'}).png().toBuffer()
  await sharp({create:{width:diagramWidth,height:diagramHeight,channels:3,background:'#43535c'}})
    .composite([{input:sprite,left:0,top:28},{input:drawJoints(arms,scale,diagramWidth,diagramHeight)}])
    .png().toFile(path.join(review,'joint-sheet.png'))

  const frames = await Promise.all(cells.map(cell => raw(cell,cellSize,cellSize)
    .resize(192,192,{kernel:'nearest'}).raw().toBuffer()))
  const gifPath = path.join(review,'swing-192.gif')
  await raw(Buffer.concat(frames),192,192*frames.length,{pageHeight:192})
    .gif({delay:delays,loop:0,dither:0}).toFile(gifPath)
  const gif = await sharp(gifPath,{animated:true}).metadata()
  assert.deepEqual([gif.width,gif.pageHeight,gif.pages,gif.delay],[192,192,6,delays])

  const comparisonPath = path.join(root,'game/assets/combat/r2sf6-attack-front-right.png')
  const existing = await sharp(comparisonPath).ensureAlpha().raw().toBuffer()
  assert.equal(existing.length,pixels.length)
  await raw(Buffer.concat([existing,pixels]),width,height*2).resize(width*2,height*4,{kernel:'nearest'})
    .flatten({background:'#43535c'}).png().toFile(path.join(review,'before-after.png'))
  const report = {size:[width,height], pivot:[48,80], starts, delays, contacts,
    poses:arms.map((arm,i)=>({name:names[i],arm,tip:source[i-1]?.tip ?? null,estimated:i === 0}))}
  await fs.writeFile(path.join(review,'joints.json'),JSON.stringify(report,null,2)+'\n')
  console.log(JSON.stringify(report))
}

main().catch(error => {console.error(error);process.exitCode=1})
