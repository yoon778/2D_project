// Eight supplied views, native articulated legs, fixed-foot recoil, one static corpse.
const fs=require('node:fs/promises'),path=require('node:path'),sharp=require('sharp')
const r=require('./raster.cjs'),config=require('./r2z-rig.json'),sourceConfig=require('./r2z-source.json')
const walkConfig=require('../player/consistent-rig.json'),{joints}=require('../player/consistent-walk.cjs')
const root=path.resolve(__dirname,'../..'),size=80
function rectangle([x0,y0,x1,y1]){return[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]}
function color(b,x,y){return b.subarray((y*80+x)*4,(y*80+x)*4+3).toString('hex')}
function handCoverage(source,rig){
  const b=Buffer.alloc(source.length),dark=['15141b','151316','201d21','353139','2b282b','312f3a']
  for(let y=rig.hipY;y<60;y++)for(let x=0;x<80;x++){
    const p=(y*80+x)*4
    if(!source[p+3]||!rig.hands.some(box=>r.contains(x,y,rectangle(box))))continue
    const skin=config.skin.includes(color(source,x,y)),edge=dark.includes(color(source,x,y))&&[-1,0,1].some(dy=>[-1,0,1].some(dx=>x+dx>=0&&x+dx<80&&y+dy>=0&&y+dy<80&&config.skin.includes(color(source,x+dx,y+dy))))
    if(skin||edge)source.copy(b,p,p,p+4)
  }
  return b
}
function legPart(source,coverage,bounds,repairs){
  const b=r.cut(source,rectangle(bounds))
  for(let y=bounds[1];y<bounds[3];y++)for(let x=bounds[0];x<bounds[2];x++){
    const p=(y*80+x)*4
    if(!b[p+3]||!coverage[p+3])continue
    let best=Infinity,from=null
    for(let dy=-3;dy<=3;dy++)for(let xx=24;xx<=55;xx++){
      const yy=y+dy,q=(yy*80+xx)*4
      if(yy<45||yy>62||!source[q+3]||coverage[q+3]||!config.trousers.includes(color(source,xx,yy)))continue
      const distance=Math.abs(xx-x)+Math.abs(dy)*2
      if(distance<best){best=distance;from=q}
    }
    if(from===null)throw new Error('Missing same-view trouser material under an occluded hand')
    source.copy(b,p,from,from+4);repairs.push({target:[x,y],source:[from/4%80,Math.floor(from/320)]})
  }
  return b
}
function drawLeg(rig,parts,side,points){
  const leg=rig.legs[side],material=rig.legs[leg.textureFrom||side],p=parts[side],b=Buffer.alloc(80*80*4)
  r.rotate(b,p.boot,material.ankle,points.ankle,points.pitch||0)
  r.segment(b,p.shin,material.knee,material.ankle,points.knee,points.ankle)
  r.segment(b,p.thigh,material.hip,material.knee,points.hip,points.knee)
  r.outline(b,config.outline,Math.floor(points.hip[1])+3)
  return b
}
function resumePoses(state) {
  const {rig, parts, upper} = state
  const near = rig.nearLeg
  const far = near === 'right' ? 'left' : 'right'
  return state.walk.map((_, phase) => [1/3, 2/3].map(progress => {
    const pose = Buffer.alloc(size * size * 4)
    for (const side of [far, near]) {
      const leg = rig.legs[side]
      const target = joints(rig, leg, phase)
      const interpolate = (start, end) => start.map((value, axis) => value + (end[axis] - value) * progress)
      r.overlay(pose, drawLeg(rig, parts, side, {
        hip: interpolate(leg.hip, target.hip),
        knee: interpolate(leg.knee, target.knee),
        ankle: interpolate(leg.ankle, target.ankle),
        pitch: target.pitch * progress,
      }))
    }
    r.overlay(pose, upper, 0, walkConfig.bodyDrop[phase] * progress)
    return pose
  }))
}
function body(source,rig,coverage){
  const b=Buffer.from(source)
  for(let y=rig.hipY;y<80;y++)for(let x=0;x<80;x++){
    const p=(y*80+x)*4
    if(coverage[p+3]||(y<rig.hipY+2&&config.shirt.includes(color(source,x,y))))continue
    b.fill(0,p,p+4)
  }
  return b
}
async function build(facing,source,options={}){
  const rig=config.facings[facing],coverage=handCoverage(source,rig),upper=body(source,rig,coverage),parts={},repairs=[]
  const directory=path.join(__dirname,'parts',facing.replaceAll('_','-'))
  if(options.writeParts!==false)await fs.mkdir(directory,{recursive:true})
  for(const side of ['right','left']){
    const material=rig.legs[rig.legs[side].textureFrom||side];parts[side]={}
    for(const name of ['thigh','shin','boot']){
      parts[side][name]=legPart(source,coverage,material[name],repairs)
      if(options.writeParts!==false)await r.png(parts[side][name],80,80,path.join(directory,`${side}-${name}.png`))
    }
  }
  if(options.writeParts!==false){await r.png(upper,80,80,path.join(directory,'body.png'));await r.png(coverage,80,80,path.join(directory,'hand-coverage.png'))}
  const near=rig.nearLeg,far=near==='right'?'left':'right',walking=[],hit=[]
  for(let phase=0;phase<8;phase++){
    const b=Buffer.alloc(80*80*4)
    for(const side of [far,near])r.overlay(b,drawLeg(rig,parts,side,joints(rig,rig.legs[side],phase)))
    r.overlay(b,upper,0,walkConfig.bodyDrop[phase]);walking.push(b)
  }
  const length=Math.hypot(...rig.worldFacing),ground=[rig.worldFacing[0]/length,rig.worldFacing[1]/length*.6],pivot=[(rig.legs.right.hip[0]+rig.legs.left.hip[0])/2,rig.hipY]
  for(let stage=0;stage<3;stage++){
    const amount=[1.5,3,1][stage],shift=ground.map(v=>-v*amount),b=Buffer.alloc(80*80*4)
    for(const side of [far,near]){
      const leg=rig.legs[side],points={hip:leg.hip.map((v,i)=>v+shift[i]),knee:leg.knee.map((v,i)=>v+shift[i]*.35),ankle:leg.ankle,pitch:0}
      r.overlay(b,drawLeg(rig,parts,side,points))
    }
    r.rotate(b,upper,pivot,pivot.map((v,i)=>v+shift[i]),-Math.sign(rig.worldFacing[0]||1)*[2,5,1][stage])
    // Keep the supplied soles/ground contact exact throughout the short recoil.
    source.copy(b,66*80*4,66*80*4);hit.push(b)
  }
  hit.push(Buffer.from(source))
  return{idle:source,walk:walking,hit,upper,parts,repairs,rig}
}
function corpse(state){
  const b=Buffer.alloc(80*80*4),{rig,parts,upper}=state,pivot=[(rig.legs.right.hip[0]+rig.legs.left.hip[0])/2,rig.hipY]
  const poses={right:{hip:[35,53],knee:[23,55],ankle:[14,63],pitch:90},left:{hip:[35,61],knee:[26,65],ankle:[17,68],pitch:90}}
  for(const side of ['left','right'])r.overlay(b,drawLeg(rig,parts,side,poses[side]))
  r.rotate(b,upper,pivot,[35,57],90)
  return b
}
async function sheet(cells,columns,file,scale=3){
  const width=columns*80,height=Math.ceil(cells.length/columns)*80,b=Buffer.alloc(width*height*4)
  for(let i=0;i<cells.length;i++)for(let y=0;y<80;y++)cells[i].copy(b,((Math.floor(i/columns)*80+y)*width+i%columns*80)*4,y*320,(y+1)*320)
  await r.png(b,width,height,file,scale)
}
async function loadState(facing, legacyWalk = false) {
  const [left, top] = sourceConfig.facings[facing].sourceCell
  const source = await sharp(path.join(__dirname, config.master))
    .extract({left, top, width: size, height: size}).ensureAlpha().raw().toBuffer()
  const state = await build(facing, source, {writeParts: false})
  state.resume = resumePoses(state)
  if (facing === 'front_right' && !legacyWalk) {
    // R2-PLZ replaced only these eight walk cells, leaving the resume cells intact.
    const {data, info} = await sharp(path.join(__dirname, 'studies/front-right-walk-pixellab-80.png'))
      .ensureAlpha().raw().toBuffer({resolveWithObject: true})
    if (info.width !== size || info.height !== size * state.walk.length) {
      throw new Error('PixelLab walk sheet must contain eight 80x80 cells in one column')
    }
    const frameBytes = size * size * 4
    state.walk = state.walk.map((_, phase) => data.subarray(phase * frameBytes, (phase + 1) * frameBytes))
  }
  return state
}
async function loadStates({legacyWalk = false} = {}) {
  const states = await Promise.all(r.facings.map(facing => loadState(facing, legacyWalk)))
  return Object.fromEntries(r.facings.map((facing, index) => [facing, states[index]]))
}
async function writeComparison(facing, state, review) {
  const cells = state.resume.flatMap((steps, phase) => [state.idle, ...steps, state.walk[phase]])
  await sheet(cells, 4, path.join(review, `${facing.replaceAll('_', '-')}-resume-3x.png`))
}
async function main() {
  const review = path.join(root, 'output/review/R2-ZT-art')
  if (process.argv[2] === '--preview') {
    await writeComparison('front_right', await loadState('front_right'), review)
    return
  }
  const states = await loadStates()
  await Promise.all(r.facings.map(facing => writeComparison(facing, states[facing], review)))
  const result = await r.writeAssets(states, corpse(states.front_right), path.join(root, 'game/assets/zombie'))
  console.log(JSON.stringify({poses: 233, image: result.metadata.image, canvas: result.metadata.canvas_size, review}))
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1})
module.exports={build,corpse,loadStates}
