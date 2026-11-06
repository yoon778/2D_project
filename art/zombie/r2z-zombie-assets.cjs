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
async function main(){
  const master=await sharp(path.join(__dirname,config.master)).ensureAlpha().raw().toBuffer(),states={}
  for(const facing of r.facings){
    const[left,top]=sourceConfig.facings[facing].sourceCell,b=Buffer.alloc(80*80*4)
    for(let y=0;y<80;y++){const p=((top+y)*320+left)*4;master.copy(b,y*320,p,p+320)}
    states[facing]=await build(facing,b);console.log(`${facing}: idle1 walk8 hit4`)
  }
  const dead=corpse(states.front_right),dest=path.join(root,'game/assets/zombie'),review=path.join(root,'output/review/R2-Z-art')
  await r.writeAssets(states,dead,dest)
  await sheet(r.facings.flatMap(f=>states[f].walk),8,path.join(review,'walk-eight-directions-3x.png'))
  await sheet(r.facings.flatMap(f=>states[f].hit),4,path.join(review,'hit-eight-directions-4x.png'),4)
  await sheet([dead],1,path.join(review,'corpse-6x.png'),6)
  await fs.writeFile(path.join(review,'material-repairs.json'),JSON.stringify(Object.fromEntries(r.facings.map(f=>[f,states[f].repairs])),null,2)+'\n')
  console.log(JSON.stringify({poses:105,image:'game/assets/zombie/r2z-zombie-20261106.png',review}))
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1})
module.exports={build,corpse}
