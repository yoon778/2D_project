// Seven approved views with a directional weight shift and articulated right-hand bat.
const path = require('node:path'), sharp = require('sharp')
const {drawLeg, joints, renderWalkAtlas} = require('./consistent-walk.cjs')
const {shiftWeight} = require('../attack-weight.cjs')
const ap8 = require('./r2ap8-motion.json')
const settings = require('./r2c8-rigs.json'), walk = require('./consistent-rig.json')
const rigs = {...walk.facings, ...require('./consistent-front-back.json'), ...require('./consistent-side.json'), ...require('./consistent-diagonal.json')}
const root = path.resolve(__dirname, '../..'), size = 96
const navy = ['15141b','242633','323648','42495f','555d77','69728e']
const skin = ['15141b','392b29','5b3e35','684d42','bc8060','e9af89','ffcfaa']
const cuff = [...navy,'a54816','ef770b','ffa510','ffe276']
const names = ['anticipate_1','anticipate_mid','anticipate_2','swing_mid','hit','hit_follow_mid','follow','follow_recover_mid','recover','recover_return_1','recover_return_2','return']
const labels = ['준비 1','준비 중간','준비 2','휘두르기 중간','타격','타격 후속 중간','후속','후속 회복 중간','회복','복귀 중간 1','복귀 중간 2','복귀'], times = [0,.045,.09,.135,.18,.225,.27,.32,.37,.425,.48,.54,.60]
function inside(x,y,p) {let hit=false;for(let i=0,j=p.length-1;i<p.length;j=i++){const[a,b]=p[i],[c,d]=p[j];if((b>y)!==(d>y)&&x<(c-a)*(y-b)/(d-b)+a)hit=!hit}return hit}
function contains(x,y,m) {if(Array.isArray(m))return inside(x+.5,y+.5,m);if(m.rows){const r=m.rows[y];return r&&(Array.isArray(r[0])?r:[r]).some(([a,b])=>x>=a&&x<=b)}return inside(x+.5,y+.5,m.polygon)}
function cut(src,mask,colors,repair=false) {const b=Buffer.alloc(src.length);for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(!contains(x,y,mask))continue;const rgb=src.subarray(p,p+3).toString('hex');if(src[p+3]&&(!colors||colors.includes(rgb)))src.copy(b,p,p,p+4);else if(repair)b.set([50,54,72,255],p)}return b}
function paint(dst,src,inverse) {for(let y=0;y<size;y++)for(let x=0;x<size;x++){const[sx,sy]=inverse(x-8,y-8).map(Math.round);if(sx<0||sx>=80||sy<0||sy>=80)continue;const p=(sy*80+sx)*4;if(src[p+3])src.copy(dst,(y*size+x)*4,p,p+4)}}
function segment(dst,src,a,b,c,d) {const sl=Math.hypot(b[0]-a[0],b[1]-a[1]),tl=Math.hypot(d[0]-c[0],d[1]-c[1]),su=[(b[0]-a[0])/sl,(b[1]-a[1])/sl],tu=[(d[0]-c[0])/tl,(d[1]-c[1])/tl];paint(dst,src,(x,y)=>{const px=x-c[0],py=y-c[1],along=(px*tu[0]+py*tu[1])*sl/tl,across=-px*tu[1]+py*tu[0];return[a[0]+su[0]*along-su[1]*across,a[1]+su[1]*along+su[0]*across]})}
function rotate(dst,src,anchor,target,angle) {const c=Math.cos(angle),s=Math.sin(angle);paint(dst,src,(x,y)=>[anchor[0]+c*(x-target[0])+s*(y-target[1]),anchor[1]-s*(x-target[0])+c*(y-target[1])])}
function over(dst,src,w=96,h=96,x0=0,y0=0) {for(let y=0;y<h;y++)for(let x=0;x<w;x++){const xx=x+x0,yy=y+y0,p=(y*w+x)*4;if(xx>=0&&xx<96&&yy>=0&&yy<96&&src[p+3])src.copy(dst,(yy*96+xx)*4,p,p+4)}}
function clearRun(pixels, [x, top, bottom], width = size) {
  for (let y = top; y <= bottom; y++) {
    const p = (y * width + x) * 4
    pixels.fill(0, p, p + 4)
  }
}
function ink(b,top=0,bottom=95,protectedPixels=null) {for(let y=top;y<=bottom;y++)for(let x=0;x<96;x++){const p=(y*96+x)*4,rgb=b.subarray(p,p+3).toString('hex');if(!b[p+3]||protectedPixels?.[p+3]||['15141b','242633','392b29'].includes(rgb))continue;if([[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=96||y+dy<0||y+dy>=96||!b[((y+dy)*96+x+dx)*4+3]))b.set([21,20,27],p)}}
function hipInk(b,rig,drop,weapon) {if(!rig.hipOutline)return;for(let y=55+drop;y<=62+drop;y++)for(let x=0;x<96;x++){const p=(y*96+x)*4;if(!navy.includes(b.subarray(p,p+3).toString('hex'))||!b[p+3]||weapon?.[p+3])continue;if([[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=96||!b[((y+dy)*96+x+dx)*4+3]))b.set([21,20,27],p)}}
function padded(atlas,frame) {const b=Buffer.alloc(96*96*4);for(let y=0;y<80;y++){const p=((Math.floor(frame/4)*80+y)*320+frame%4*80)*4;atlas.copy(b,((y+8)*96+8)*4,p,p+320)}return b}
function direction(v,angle=0) {const n=Math.hypot(v[0],v[1]*.6),x=v[0]/n,y=v[1]*.6/n,c=Math.cos(angle),s=Math.sin(angle);return[x*c-y*s,x*s+y*c]}
function solve(model,grip,dir) {const palm=Math.hypot(model.hand.grip[0]-model.hand.anchor[0],model.hand.grip[1]-model.hand.anchor[1]),shoulder=model.shoulder,l1=Math.hypot(model.upper.b[0]-model.upper.a[0],model.upper.b[1]-model.upper.a[1]),l2=Math.hypot(model.fore.b[0]-model.fore.a[0],model.fore.b[1]-model.fore.a[1]);let wrist=[grip[0]-dir[0]*palm,grip[1]-dir[1]*palm],dx=wrist[0]-shoulder[0],dy=wrist[1]-shoulder[1],distance=Math.hypot(dx,dy),d=Math.min((l1+l2)*.98,Math.max(Math.abs(l1-l2)+.1,distance));if(distance<.001){dx=1;dy=0;distance=1}wrist=[shoulder[0]+dx/distance*d,shoulder[1]+dy/distance*d];const a=Math.atan2(dy,dx)+Math.acos(Math.max(-1,Math.min(1,(l1*l1+d*d-l2*l2)/(2*l1*d))));return{elbow:[shoulder[0]+l1*Math.cos(a),shoulder[1]+l1*Math.sin(a)],wrist,grip:[wrist[0]+dir[0]*palm,wrist[1]+dir[1]*palm],handAngle:Math.atan2(dir[1],dir[0])-Math.atan2(model.hand.grip[1]-model.hand.anchor[1],model.hand.grip[0]-model.hand.anchor[0])}}
function poseFor(model,rig,index,tuning) {const d=direction(rig.worldFacing),s=model.shoulder,side=s[0]>=40?1:-1;let grip,dir;
  if(index===0){grip=[s[0]+side*6,s[1]-4];dir=direction(rig.worldFacing,Math.PI)}
  else if(index===1){grip=[s[0]+side*6,s[1]-12];dir=direction(rig.worldFacing,-Math.PI/2)}
  else if(index===2){
    const [dx, dy] = tuning?.hitGrip || [0, 0]
    grip = [s[0]+d[0]*18+dx,s[1]+d[1]*13+3+dy]
    dir = direction(rig.worldFacing, (tuning?.hitAngle || 0) * Math.PI / 180)
  }
  else if(index===3){grip=model.followGrip||[s[0]+d[0]*9,s[1]+d[1]*7+8];dir=direction(rig.worldFacing,(tuning?.followAngle ?? 50)*Math.PI/180)}
  else{grip=[model.grip[0]-d[0]*2,model.grip[1]-3];dir=[.08,Math.sqrt(1-.08*.08)]}
  return {...solve(model,grip,dir),dir,behind:model.far||index<2}
}
function shortAngle(a,b,t) {return a+Math.atan2(Math.sin(b-a),Math.cos(b-a))*t}
function between(model,a,b,t) {
  const bone=(from,to,origin)=>{const angle=shortAngle(Math.atan2(from[1],from[0]),Math.atan2(to[1],to[0]),t),length=Math.hypot(...from)*(1-t)+Math.hypot(...to)*t;return[origin[0]+Math.cos(angle)*length,origin[1]+Math.sin(angle)*length]}
  const s=model.shoulder,elbow=bone([a.elbow[0]-s[0],a.elbow[1]-s[1]],[b.elbow[0]-s[0],b.elbow[1]-s[1]],s),wrist=bone([a.wrist[0]-a.elbow[0],a.wrist[1]-a.elbow[1]],[b.wrist[0]-b.elbow[0],b.wrist[1]-b.elbow[1]],elbow),handAngle=shortAngle(a.handAngle,b.handAngle,t),angle=shortAngle(Math.atan2(a.dir[1],a.dir[0]),Math.atan2(b.dir[1],b.dir[0]),t),palm=[model.hand.grip[0]-model.hand.anchor[0],model.hand.grip[1]-model.hand.anchor[1]],c=Math.cos(handAngle),sn=Math.sin(handAngle)
  return{elbow,wrist,handAngle,grip:[wrist[0]+c*palm[0]-sn*palm[1],wrist[1]+sn*palm[0]+c*palm[1]],dir:[Math.cos(angle),Math.sin(angle)],behind:a.behind}
}
function twelvePoses(model,rig,pivot,axisEnd,tuning) {
  const sourceAngle = Math.atan2(axisEnd[1] - pivot[1], axisEnd[0] - pivot[0])
  const swingDegrees = rig.batRotation?.degrees ?? 0
  const angle = sourceAngle + swingDegrees * Math.PI / 180
  const keys=Array.from({length:5},(_,i)=>poseFor(model,rig,i,tuning)),grip=rig.batRotation?.targetPivot||model.grip,palm=[model.hand.grip[0]-model.hand.anchor[0],model.hand.grip[1]-model.hand.anchor[1]],palmLength=Math.hypot(...palm),rest={elbow:model.upper.b,wrist:[grip[0]-palm[0],grip[1]-palm[1]],grip,handAngle:0,dir:[Math.cos(angle),Math.sin(angle)],behind:model.far}
  if(model.removeArm===false)rest.elbow=solve(model,grip,palm.map(v=>v/palmLength)).elbow
  // Use the carry angle at both ends of the swing, anchored to the same grip.
  const returnAngle = sourceAngle + (rig.carryBatDegrees ?? swingDegrees) * Math.PI / 180
  const returnPose = {...rest, dir: [Math.cos(returnAngle), Math.sin(returnAngle)]}
  const sequence=[keys[0],between(model,keys[0],keys[1],.5),keys[1],between(model,keys[1],keys[2],.5),keys[2],between(model,keys[2],keys[3],.5),keys[3],between(model,keys[3],keys[4],model.followRecoverFraction??.5),keys[4],between(model,keys[4],returnPose,(.425-.37)/(.54-.37)),between(model,keys[4],returnPose,(.48-.37)/(.54-.37)),{...returnPose,original:true}]
  // A small recovery arc keeps the far weapon visible between occluded leg phases.
  for(const [i,degrees]of(model.returnArcDegrees||[]).entries()){const p=sequence[9+i],a=Math.atan2(p.dir[1],p.dir[0])+degrees*Math.PI/180;p.dir=[Math.cos(a),Math.sin(a)]}
  const windup = sequence[1]
  sequence[0] = between(model, returnPose, keys[0], ap8.startup[0])
  sequence[1] = between(model, returnPose, windup, ap8.startup[1])
  if (tuning.frontOnSwing) sequence[3].behind = false
  return sequence
}
async function png(b,w,h,file,scale=1) {await sharp(b,{raw:{width:w,height:h,channels:4}}).resize(w*scale,h*scale,{kernel:'nearest'}).png().toFile(file)}
function atlas(cells,cols) {const width=cols*96,height=Math.ceil(cells.length/cols)*96,b=Buffer.alloc(width*height*4);for(let f=0;f<cells.length;f++)for(let y=0;y<96;y++)cells[f].copy(b,((Math.floor(f/cols)*96+y)*width+f%cols*96)*4,y*384,(y+1)*384);return{b,width,height}}
async function build(facing, walkAtlas) {
  const model=settings[facing],rig=rigs[facing],slug=facing.replaceAll('_','-'),[left,top,width,height]=rig.sourceCell;
  const tuning = ap8[facing]
  const src=await sharp(path.join(__dirname,'style-studies/eight-direction-consistency/turnaround-idle-64-v3.png')).extract({left,top,width,height}).ensureAlpha().raw().toBuffer(),r1=walkAtlas ?? await sharp(path.join(root,`game/assets/player/r1-consistent-${slug}-20261105.png`)).ensureAlpha().raw().toBuffer();
  const bodyRaw=await sharp(path.join(__dirname,'consistent-parts',slug,'body.png')).ensureAlpha().raw().toBuffer();
  const parts={upper:cut(src,model.upper.mask,navy,model.repairMaterial),fore:cut(src,model.fore.mask,cuff,model.repairMaterial),hand:cut(src,model.hand.mask,skin)},legParts={};
  // Wood highlights share skin colors in the approved art; geometry owns the full bat.
  const originalBat=cut(src,rig.batMask,null),donorFacing=rig.batSourceFacing||facing,donorRig=rigs[donorFacing];
  // Removal-only coverage for source outlines outside the legacy bat mask.
  if(model.oldBatExtras){const extra=cut(src,model.oldBatExtras,null);for(let p=0;p<src.length;p+=4)if(extra[p+3])extra.copy(originalBat,p,p,p+4)}
  const [donorLeft,donorTop,donorWidth,donorHeight]=donorRig.sourceCell;
  const donorSource=donorFacing===facing?src:await sharp(path.join(__dirname,'style-studies/eight-direction-consistency/turnaround-idle-64-v3.png')).extract({left:donorLeft,top:donorTop,width:donorWidth,height:donorHeight}).ensureAlpha().raw().toBuffer();
  const bat=cut(donorSource,donorRig.batMask,null);
  // The broad front-left donor mask includes a detached sliver of the boot.
  for (const run of tuning.batFragments || []) clearRun(bat, run, 80)
  let maxY=-1,tipXs=[];for(let y=0;y<80;y++)for(let x=0;x<80;x++)if(bat[(y*80+x)*4+3]){if(y>maxY){maxY=y;tipXs=[]}if(y===maxY)tipXs.push(x)}
  const pivot=donorRig.batRotation?.pivot||model.grip,axisEnd=donorRig.batRotation?.axisEnd||[tipXs.reduce((s,x)=>s+x,0)/tipXs.length,maxY];
  for(const side of['right','left']){legParts[side]={};for(const name of['thigh','shin','boot'])legParts[side][name]=await sharp(path.join(__dirname,'consistent-parts',slug,`${side}-${name}.png`)).ensureAlpha().raw().toBuffer()}
  if(rig.legFacet)for(const name of['thigh','shin']){const b=legParts[rig.legFacet.side][name],f=rig.legFacet,to=[0,2,4].map(n=>parseInt(f.to.slice(n,n+2),16));for(let y=f.y[0];y<=f.y[1];y++)for(let x=f.x[0];x<=f.x[1];x++){const p=(y*80+x)*4;if(b[p+3]&&b.subarray(p,p+3).toString('hex')===f.from)b.set(to,p)}}
  const upper=Buffer.from(bodyRaw),armMask=Buffer.alloc(src.length);if(model.removeArm!==false)for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4,extraFore=contains(x,y,model.fore.mask)&&model.removeForeColors?.includes(src.subarray(p,p+3).toString('hex'));if(parts.upper[p+3]||parts.fore[p+3]||(src[p+3]&&(contains(x,y,model.hand.removeMask||model.hand.mask)||extraFore)))armMask[p+3]=255}
  const core=(x,y)=>x>=model.core[0]&&x<model.core[2]&&y>=model.core[1]&&y<model.core[3];
  for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if((armMask[p+3]||originalBat[p+3])&&upper[p+3]){if(core(x,y))upper.set([50,54,72,255],p);else upper.fill(0,p,p+4)}}
  const upperCell=Buffer.alloc(96*96*4),head=Buffer.alloc(src.length),gear=Buffer.alloc(src.length);paint(upperCell,upper,(x,y)=>[x,y]);
  for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(y<=26)src.copy(head,p,p,p+4);if(model.equipment&&x>=model.equipment[0]&&x<model.equipment[2]&&y>=model.equipment[1]&&y<model.equipment[3]&&!navy.slice(1).includes(src.subarray(p,p+3).toString('hex')))src.copy(gear,p,p,p+4)}
  const headCell=Buffer.alloc(96*96*4),gearCell=Buffer.alloc(headCell.length);paint(headCell,head,(x,y)=>[x,y]);paint(gearCell,gear,(x,y)=>[x,y]);
  const oldWeapon=Buffer.alloc(96*96*4);if(rig.batRotation){const r=rig.batRotation,g=r.targetPivot||r.pivot,angle=r.degrees*Math.PI/180,dx=(axisEnd[0]-r.pivot[0])*(r.lengthScale||1),dy=(axisEnd[1]-r.pivot[1])*(r.lengthScale||1);segment(oldWeapon,bat,r.pivot,axisEnd,g,[g[0]+Math.cos(angle)*dx-Math.sin(angle)*dy,g[1]+Math.sin(angle)*dx+Math.cos(angle)*dy])}else paint(oldWeapon,originalBat,(x,y)=>[x,y]);
  const restingLegs=Buffer.alloc(96*96*4),far=rig.nearLeg==='right'?'left':'right',hipBand=rig.hipOutline?[Math.min(rig.legs.right.hip[1],rig.legs.left.hip[1])-2,Math.max(rig.legs.right.hip[1],rig.legs.left.hip[1])+5]:null;
  for(const side of[far,rig.nearLeg])over(restingLegs,drawLeg(rig,legParts,side,{...rig.legs[side],pitch:0},hipBand),80,80,8,8);
  const idle = padded(r1, 8)
  // Extract the attack torso from the original idle so the carry change stays out of the swing.
  const attackIdle = rig.carryBatDegrees === undefined ? idle : padded(await renderWalkAtlas(facing, {carryBatDegrees: undefined}), 8)
  const staticBody=Buffer.from(attackIdle);for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4,q=((y+8)*96+x+8)*4,isBat=oldWeapon[q+3];if(armMask[p+3]||isBat){if(armMask[p+3]&&core(x,y))staticBody.set([50,54,72,255],q);else if(y>=Math.min(rig.legs.right.hip[1],rig.legs.left.hip[1]))restingLegs.copy(staticBody,q,q,q+4);else staticBody.fill(0,q,q+4)}}
  const shoulder = model.shoulder.map((value, i) => value + (tuning.shoulderOffset?.[i] || 0))
  const stationary = [], moving = [], layers = []
  const poses = twelvePoses({...model, shoulder}, rig, pivot, axisEnd, tuning)
  if (tuning.bodyFragment) {
    clearRun(staticBody, tuning.bodyFragment)
    clearRun(upperCell, tuning.bodyFragment)
  }
  if (tuning.walkingBodyFragment) clearRun(upperCell, tuning.walkingBodyFragment)
  const [forwardX, forwardY] = rig.worldFacing
  const depth = forwardY * (forwardX ? .6 : 1)
  for(let a=0;a<12;a++){
    if(a===11){stationary.push(idle);for(let w=0;w<8;w++)moving.push(padded(r1,w));continue}
    const travel = ap8.travel[a]
    const weight = tuning.weights?.[a] || [Math.round(forwardX * travel), Math.round(depth * travel + ap8.crouch[a])]
    const [dx, dy] = weight
    const shifted = ([x, y]) => [x + dx, y + dy]
    const pose = poses[a], arm = Buffer.alloc(size * size * 4), weapon = Buffer.alloc(arm.length)
    const elbow = shifted(pose.elbow), wrist = shifted(pose.wrist), grip = shifted(pose.grip)
    segment(arm, parts.upper, model.upper.a, model.upper.b, shifted(shoulder), elbow)
    segment(arm, parts.fore, model.fore.a, model.fore.b, elbow, wrist)
    rotate(arm, parts.hand, model.hand.anchor, wrist, pose.handAngle)
    ink(arm)
    const end = grip.map((value, axis) => value + pose.dir[axis] * model.length)
    segment(weapon, bat, pivot, axisEnd, grip, end)
    ink(weapon)
    const lean = (part, drop = 0) => shiftWeight(part, size, 8 + drop, weight, 53, 63)
    const torso = lean(upperCell), head = lean(headCell), gear = Buffer.alloc(arm.length)
    // Keep the visible left hand and parcel together through the body lean.
    over(gear, gearCell, size, size, dx, dy)
    layers.push({arm, weapon, grip, end, weight, gear})
    const stand = Buffer.alloc(arm.length), body = lean(staticBody)
    for (const layer of pose.behind ? [weapon, arm, body] : [body, arm, weapon]) over(stand, layer)
    over(stand, head)
    over(stand, gear)
    hipInk(stand, rig, 0, weapon)
    stationary.push(stand)
    for (let w = 0; w < 8; w++) {
      const frame = Buffer.alloc(arm.length), legs = Buffer.alloc(arm.length), drop = walk.bodyDrop[w]
      const band = hipBand?.map(y => y + drop)
      if (pose.behind) over(frame, weapon, size, size, 0, drop)
      for (const side of [far, rig.nearLeg]) {
        const leg = rig.legs[side]
        const points = joints(rig, leg, w)
        if (tuning.walkLegJointShift) {
          // Move the pelvis with the torso while keeping each boot on its walk-phase anchor.
          const kneeWeight = Math.max(0, Math.min(1, (63 - points.knee[1]) / 10))
          points.hip = shifted(points.hip)
          points.knee = [points.knee[0] + dx * kneeWeight, points.knee[1] + dy * kneeWeight]
        }
        over(legs, drawLeg(rig, legParts, side, points, band, leg.walkFit), 80, 80, 8, 8)
      }
      const leaningLegs = tuning.walkLegJointShift ? legs : lean(legs, drop)
      const ankle = tuning.ankleSeams?.[w]
      if (ankle) {
        const [x, y] = ankle, p = (y * size + x) * 4
        if (!leaningLegs[p + 3]) leaningLegs.set([21, 20, 27, 255], p)
      }
      over(frame, leaningLegs)
      if (pose.behind) over(frame, arm, size, size, 0, drop)
      over(frame, torso, size, size, 0, drop)
      if (!pose.behind) {
        over(frame, arm, size, size, 0, drop)
        over(frame, weapon, size, size, 0, drop)
      }
      over(frame, head, size, size, 0, drop)
      over(frame, gear, size, size, 0, drop)
      const protectedWeapon = Buffer.alloc(arm.length)
      over(protectedWeapon, weapon, size, size, 0, drop)
      hipInk(frame, rig, drop, protectedWeapon)
      moving.push(frame)
    }
  }
  const image=`r2c8-attack-${slug}-20261106.png`,walkImage=`r2c8-attack-walk-${slug}-20261106.png`
  const common={facing,cell_size:[96,96],scale:2,reference_height:64};
  return{facing,stationary,moving,poses,layers,attack:{...common,image,canvas_size:[384,288],frames:names.map((name,a)=>({name,label:labels[a],start:times[a],end:times[a+1],clip_topleft:[a%4*96,Math.floor(a/4)*96,96,96],foot_pivot_topleft:[a%4*96+48,Math.floor(a/4)*96+80]}))},attack_walk:{...common,image:walkImage,canvas_size:[768,1152],attack_steps:12,walk_phases:8,frames:moving.map((_,i)=>({name:`${names[Math.floor(i/8)]}_walk${i%8+1}`,attack_index:Math.floor(i/8),walk_frame_index:i%8+1,clip_topleft:[i%8*96,Math.floor(i/8)*96,96,96],foot_pivot_topleft:[i%8*96+48,Math.floor(i/8)*96+80]}))}}
}
async function main() {
  const dest = path.join(root, 'game/assets/combat')
  for (const facing of Object.keys(settings)) {
    const result = await build(facing)
    for (const [sprites, columns, {image}] of [[result.stationary, 4, result.attack], [result.moving, 8, result.attack_walk]]) {
      const sheet = atlas(sprites, columns)
      await png(sheet.b, sheet.width, sheet.height, path.join(dest, image))
    }
    console.log(facing + ': 12 + 96 poses saved')
  }
}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1})
module.exports = {build, times}
