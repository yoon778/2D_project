// New attack-only resources; existing zombie/player inputs are read-only.
const fs=require('node:fs/promises'),path=require('node:path'),sharp=require('sharp')
const r=require('./raster.cjs'),settings=require('./r2za-rigs.json'),sourceConfig=require('./r2z-source.json'),oldRig=require('./r2z-rig.json')
const {shiftWeight} = require('../attack-weight.cjs')
const ap8 = require('./r2ap8-motion.json')
const root=path.resolve(__dirname,'../..'),review=path.join(root,'output/review/R2-AP8'),times=[0,.04,.08,.12,.16,.23,.30,.40,.46,.52,.64,.72,.80]
function solve(model,target,degrees){
  const a=degrees*Math.PI/180,dir=[Math.cos(a),Math.sin(a)],palm=Math.hypot(model.tip[0]-model.wrist[0],model.tip[1]-model.wrist[1]),l1=Math.hypot(model.elbow[0]-model.shoulder[0],model.elbow[1]-model.shoulder[1]),l2=Math.hypot(model.wrist[0]-model.elbow[0],model.wrist[1]-model.elbow[1]),s=model.shoulder
  const wanted=[target[0]-dir[0]*palm,target[1]-dir[1]*palm],dx=wanted[0]-s[0],dy=wanted[1]-s[1],distance=Math.hypot(dx,dy),d=Math.min((l1+l2)*.985,Math.max(Math.abs(l1-l2)+.1,distance)),wrist=[s[0]+dx/distance*d,s[1]+dy/distance*d],angle=Math.atan2(dy,dx)+(model.bend||1)*Math.acos(Math.max(-1,Math.min(1,(l1*l1+d*d-l2*l2)/(2*l1*d))))
  return{elbow:[s[0]+Math.cos(angle)*l1,s[1]+Math.sin(angle)*l1],wrist,tip:[wrist[0]+dir[0]*palm,wrist[1]+dir[1]*palm],handAngle:(a-Math.atan2(model.tip[1]-model.wrist[1],model.tip[0]-model.wrist[0]))*180/Math.PI}
}
function shortAngle(a,b,t){return a+Math.atan2(Math.sin(b-a),Math.cos(b-a))*t}
function middlePose(model,a,b,t){
  const bone=(u,v,origin,length)=>{const angle=shortAngle(Math.atan2(u[1],u[0]),Math.atan2(v[1],v[0]),t);return[origin[0]+Math.cos(angle)*length,origin[1]+Math.sin(angle)*length]},s=model.shoulder,l1=Math.hypot(model.elbow[0]-s[0],model.elbow[1]-s[1]),l2=Math.hypot(model.wrist[0]-model.elbow[0],model.wrist[1]-model.elbow[1])
  const elbow=bone([a.elbow[0]-s[0],a.elbow[1]-s[1]],[b.elbow[0]-s[0],b.elbow[1]-s[1]],s,l1),wrist=bone([a.wrist[0]-a.elbow[0],a.wrist[1]-a.elbow[1]],[b.wrist[0]-b.elbow[0],b.wrist[1]-b.elbow[1]],elbow,l2),angle=shortAngle(a.handAngle*Math.PI/180,b.handAngle*Math.PI/180,t),dx=model.tip[0]-model.wrist[0],dy=model.tip[1]-model.wrist[1]
  return{elbow,wrist,tip:[wrist[0]+Math.cos(angle)*dx-Math.sin(angle)*dy,wrist[1]+Math.sin(angle)*dx+Math.cos(angle)*dy],handAngle:angle*180/Math.PI}
}
function twelvePoses(config){
  const keys=Array.from({length:7},(_,phase)=>Object.fromEntries(Object.entries(config.arms).map(([side,model])=>[side,solve(model,model.targets[phase],model.angles[phase])]))),middle=(from,to,row)=>Object.fromEntries(Object.entries(config.arms).map(([side,model])=>[side,middlePose(model,keys[from][side],keys[to][side],config.middle?.[row]?.[side]?.fraction??config.middle?.[row]?.fraction??.5)]))
  return[keys[0],middle(0,1,1),keys[1],middle(1,2,3),keys[2],middle(2,3,5),keys[3],keys[4],middle(4,5,8),keys[5],keys[6],{original:true}]
}
function directionalAttack(facing, config) {
  const [forwardX, forwardY] = oldRig.facings[facing].worldFacing
  const depth = forwardY * (forwardX ? .6 : 1)
  const override = ap8.overrides[facing]
  const weights = ap8.travel.map((travel, i) =>
    override?.weights?.[i] || [Math.round(forwardX * travel), Math.round(depth * travel + ap8.crouch[i])])
  const arms = Object.fromEntries(Object.entries(config.arms).map(([side, arm]) => {
    const idleAngle = Math.atan2(arm.tip[1] - arm.wrist[1], arm.tip[0] - arm.wrist[0])
    const targets = arm.targets.map(([x, y], i) => override?.[side]?.targets?.[i] || [
      arm.tip[0] + (x - arm.tip[0]) * ap8.tuck[i] + forwardX * ap8.aimTravel[i],
      arm.tip[1] + (y - arm.tip[1]) * ap8.tuck[i] + depth * ap8.aimTravel[i],
    ])
    const angles = arm.angles.map((angle, i) => override?.[side]?.angles?.[i] ??
      shortAngle(idleAngle, angle * Math.PI / 180, ap8.tuck[i]) * 180 / Math.PI)
    return [side, {targets, angles}]
  }))
  return {weights, ...arms}
}
async function sourceCell(facing){
  const[left,top,width,height]=sourceConfig.facings[facing].sourceCell
  return sharp(path.join(__dirname,oldRig.master)).extract({left,top,width,height}).ensureAlpha().raw().toBuffer()
}
function cutSkin(source,mask){
  const b=Buffer.alloc(source.length),dark=['15141b','151316','201d21','2b282b','353139','312f3a','504c42','3d3836','4e4038','645e4f']
  const skin=(x,y)=>x>=0&&x<80&&y>=0&&y<80&&source[(y*80+x)*4+3]&&oldRig.skin.includes(source.subarray((y*80+x)*4,(y*80+x)*4+3).toString('hex'))
  for(let y=0;y<80;y++)for(let x=0;x<80;x++){
    const p=(y*80+x)*4,c=source.subarray(p,p+3).toString('hex')
    if(source[p+3]&&r.contains(x,y,mask)&&(skin(x,y)||(dark.includes(c)&&[[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>skin(x+dx,y+dy)))))source.copy(b,p,p,p+4)
  }
  return b
}
function fillCore(source,removed,x,y,colors=oldRig.shirt){
  let best=Infinity,from=null
  for(let yy=Math.max(27,y-3);yy<Math.min(63,y+4);yy++)for(let xx=26;xx<=54;xx++){
    const q=(yy*80+xx)*4,c=source.subarray(q,q+3).toString('hex')
    if(!source[q+3]||removed[q+3]||!colors.includes(c))continue
    const distance=Math.abs(xx-x)+Math.abs(yy-y)*2
    if(distance<best){best=distance;from=q}
  }
  return from
}
function overlayArmEdge(sprite, torso, arm, side, start, end, width) {
  const direction = side === 'left' ? 1 : -1
  for (let y = start; y < end; y++) {
    let x = side === 'left' ? 0 : 79
    while (x >= 0 && x < 80 && !torso[(y * 80 + x) * 4 + 3]) x += direction
    for (let i = 0; i < width && x >= 0 && x < 80; i++, x += direction) {
      const p = (y * 80 + x) * 4
      if (torso[p + 3] && arm[p + 3]) arm.copy(sprite, p, p, p + 4)
    }
  }
}
async function build(facing,options={}){
  const config=settings[facing],source=await sourceCell(facing),base=Buffer.from(source),removed=Buffer.alloc(source.length),repaired=Buffer.alloc(source.length),parts={}
  for(const[side,arm]of Object.entries(config.arms)){
    const material=config.arms[arm.textureFrom||side]
    parts[side]={}
    for(const name of ['upper','fore','hand']){
      const b=name==='upper'?r.cut(source,material[name]):cutSkin(source,material[name]);parts[side][name]=b
      // Removal owns the full source coverage, including dark finger/sleeve edges.
      for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(source[p+3]&&r.contains(x,y,arm[name]))removed[p+3]=255}
      if(options.writeParts){await r.png(b,80,80,path.join(__dirname,'r2za-parts',facing.replaceAll('_','-'),`${side}-${name}.png`))}
    }
  }
  if(config.sourceCleanup)for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(source[p+3]&&r.contains(x,y,config.sourceCleanup))removed[p+3]=255}
  for(let y=0;y<config.protectFromY;y++)for(let x=0;x<80;x++){
    const p=(y*80+x)*4
    if(!removed[p+3])continue
    if(y>=config.waistY){if(r.contains(x,y,config.pantsRestore)){const offset=config.pantsTextureOffset||[0,0],from=fillCore(source,removed,x+offset[0],y+offset[1],['353139','2b282b','312f3a']);if(from!==null){source.copy(base,p,from,from+4);repaired[p+3]=255;continue}}base.fill(0,p,p+4);continue}
    if(x>=config.core[0]&&x<config.core[2]&&y>=config.core[1]&&y<config.core[3]){const from=fillCore(source,removed,x,y);if(from!==null){source.copy(base,p,from,from+4);repaired[p+3]=255;continue}}
    base.fill(0,p,p+4)
  }
  for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(repaired[p+3]&&[[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=80||y+dy<0||y+dy>=80||!base[((y+dy)*80+x+dx)*4+3]))base.set([21,20,27],p)}
  const adjustments = facing === 'front_right'
    ? (options.r2ap === false ? null : require('./r2ap-front-right.json'))
    : (options.r2ap8 === false ? null : directionalAttack(facing, config))
  const poseConfig = adjustments ? {...config, arms: Object.fromEntries(Object.entries(config.arms)
    .map(([side, model]) => [side, {...model, ...adjustments[side]}]))} : config
  const frames=[],poses=twelvePoses(poseConfig),layers=[]
  for(let phase=0;phase<12;phase++){
    if(phase===11){frames.push(Buffer.from(source));layers.push({});continue}
    const arms={},pose=poses[phase]
    const weight = adjustments?.weights[phase] || [0, 0]
    const shift = ([x, y]) => [x + weight[0], y + weight[1]]
    const torso = adjustments ? shiftWeight(base, 80, 0, weight, 43, config.protectFromY) : base
    for(const[side,model]of Object.entries(config.arms)){
      const material=config.arms[model.textureFrom||side],p=parts[side],b=Buffer.alloc(source.length),j=pose[side]
      r.segment(b,p.upper,material.shoulder,material.elbow,shift(model.shoulder),shift(j.elbow));r.segment(b,p.fore,material.elbow,material.wrist,shift(j.elbow),shift(j.wrist));r.rotate(b,p.hand,material.wrist,shift(j.wrist),j.handAngle);r.outline(b,oldRig.outline);arms[side]=b
    }
    const b=Buffer.alloc(source.length),near=config.nearArm,far=near==='right'?'left':'right'
    if(config.bothFront){r.overlay(b,torso);r.overlay(b,arms[far]);r.overlay(b,arms[near])}
    else{r.overlay(b,arms[far]);if(config.bothBehind)r.overlay(b,arms[near]);r.overlay(b,torso);if(!config.bothBehind)r.overlay(b,arms[near])}
    const edgeWidth = adjustments && config.armEdgeWidths?.[phase]
    if (edgeWidth) {
      // Keep the reaching arms behind the center of the back, with visible side contours.
      for (const side of [far, near]) {
        const top = config.arms[side].shoulder[1] + weight[1] - 1
        overlayArmEdge(b, torso, arms[side], side, top, config.protectFromY, edgeWidth)
      }
    }
    // Ground-contact rows stay exactly as in the approved idle image.
    source.copy(b,config.protectFromY*80*4,config.protectFromY*80*4)
    frames.push(b);layers.push(arms)
  }
  if(options.writeParts){await r.png(base,80,80,path.join(__dirname,'r2za-parts',facing.replaceAll('_','-'),'body.png'));await r.png(removed,80,80,path.join(__dirname,'r2za-parts',facing.replaceAll('_','-'),'source-arm-mask.png'))}
  return{facing,source,base,removed,repaired,parts,frames,poses,layers,weights:adjustments?.weights}
}
async function sheet(cells,cols,file,scale=4){
  const width=cols*80,height=Math.ceil(cells.length/cols)*80,b=Buffer.alloc(width*height*4)
  for(let i=0;i<cells.length;i++)for(let y=0;y<80;y++)cells[i].copy(b,((Math.floor(i/cols)*80+y)*width+i%cols*80)*4,y*320,(y+1)*320)
  await fs.mkdir(path.dirname(file),{recursive:true});await sharp(b,{raw:{width,height,channels:4}}).flatten({background:'#617680'}).resize(width*scale,height*scale,{kernel:'nearest'}).png().toFile(file)
}
async function makeAtlas(options={}){
  if(r.facings.some(f=>!settings[f]))throw new Error('All eight approved attack rigs required for the production atlas')
  const pixels=Buffer.alloc(640*960*4),metadata={image:'r2za-zombie-attack-20261106.png',canvas_size:[640,960],cell_size:[80,80],scale:2,reference_height:64,facings:{}},results=[]
  for(const[col,name]of r.facings.entries()){
    const result=await build(name,{writeParts:options.writeParts===true,r2ap:options.r2ap,r2ap8:options.r2ap8});results.push(result);metadata.facings[name]=result.frames.map((b,row)=>{for(let y=0;y<80;y++)b.copy(pixels,((row*80+y)*640+col*80)*4,y*320,(y+1)*320);return{clip_topleft:[col*80,row*80,80,80],foot_pivot_topleft:[col*80+40,row*80+72],opaque_rows:r.opaqueRows(b),start:times[row],end:times[row+1]}})
  }
  return{pixels,metadata,results}
}
async function main(){
  const index=process.argv.indexOf('--facing'),facing=index>=0?process.argv[index+1]:null
  if(facing){const result=await build(facing);await sheet(result.frames,4,path.join(review,`${facing.replaceAll('_','-')}-attack-twelve-4x.png`));await sheet([result.source,...result.frames],13,path.join(review,`${facing.replaceAll('_','-')}-compare-3x.png`),3);const previous=await fs.readFile(path.join(review,'previous/r2za-zombie-attack-20261106.png')).catch(error=>{if(error.code==='ENOENT')return null;throw error});if(previous){const data=await sharp(previous).ensureAlpha().raw().toBuffer(),col=r.facings.indexOf(facing),old=[];for(let row=0;row<8;row++){const b=Buffer.alloc(25600);for(let y=0;y<80;y++){const p=((row*80+y)*640+col*80)*4;data.copy(b,y*320,p,p+320)}old.push(b)}await sheet([...old,...[0,2,4,6,7,9,10,11].map(i=>result.frames[i])],8,path.join(review,`${facing.replaceAll('_','-')}-old-eight-vs-keys-3x.png`),3)}await fs.writeFile(path.join(review,`${facing}-joints.json`),JSON.stringify(result.poses,null,2)+'\n');console.log(JSON.stringify({facing,preview:true,poses:12,review}));return}
  const{pixels,metadata,results}=await makeAtlas(),dest=path.join(root,'game/assets/zombie');await r.png(pixels,640,960,path.join(dest,metadata.image));await fs.writeFile(path.join(dest,'r2za-zombie-attack-20261106.json'),JSON.stringify(metadata,null,2)+'\n');await sheet(results.flatMap(x=>x.frames),12,path.join(review,'attack-eight-directions-3x.png'),3);await sheet(results.flatMap(x=>[1,3,5,8].map(i=>x.frames[i])),4,path.join(review,'middle-four-eight-directions-4x.png'),4);await fs.writeFile(path.join(review,'pose-joints.json'),JSON.stringify(Object.fromEntries(results.map(x=>[x.facing,x.poses])),null,2)+'\n');console.log(JSON.stringify({poses:96,review}))
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1})
module.exports={build,sourceCell,solve,times,makeAtlas}
