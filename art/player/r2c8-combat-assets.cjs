// Seven approved views; only right-arm joints and a held weapon are transformed.
const fs = require('node:fs/promises'), path = require('node:path'), sharp = require('sharp')
const {drawLeg, joints} = require('./consistent-walk.cjs')
const settings = require('./r2c8-rigs.json'), walk = require('./consistent-rig.json')
const rigs = {...walk.facings, ...require('./consistent-front-back.json'), ...require('./consistent-side.json'), ...require('./consistent-diagonal.json')}
const root = path.resolve(__dirname, '../..'), size = 96
const navy = ['15141b','242633','323648','42495f','555d77','69728e']
const skin = ['15141b','392b29','5b3e35','684d42','bc8060','e9af89','ffcfaa']
const cuff = [...navy,'a54816','ef770b','ffa510','ffe276']
const names = ['anticipate_1','anticipate_2','hit','follow','recover','return']
const labels = ['준비 1','준비 2','타격','후속','회복','복귀'], times = [0,.09,.18,.27,.37,.48,.60]
function inside(x,y,p) {let hit=false;for(let i=0,j=p.length-1;i<p.length;j=i++){const[a,b]=p[i],[c,d]=p[j];if((b>y)!==(d>y)&&x<(c-a)*(y-b)/(d-b)+a)hit=!hit}return hit}
function contains(x,y,m) {if(Array.isArray(m))return inside(x+.5,y+.5,m);if(m.rows){const r=m.rows[y];return r&&(Array.isArray(r[0])?r:[r]).some(([a,b])=>x>=a&&x<=b)}return inside(x+.5,y+.5,m.polygon)}
function cut(src,mask,colors,repair=false) {const b=Buffer.alloc(src.length);for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(!contains(x,y,mask))continue;const rgb=src.subarray(p,p+3).toString('hex');if(src[p+3]&&(!colors||colors.includes(rgb)))src.copy(b,p,p,p+4);else if(repair)b.set([50,54,72,255],p)}return b}
function paint(dst,src,inverse) {for(let y=0;y<size;y++)for(let x=0;x<size;x++){const[sx,sy]=inverse(x-8,y-8).map(Math.round);if(sx<0||sx>=80||sy<0||sy>=80)continue;const p=(sy*80+sx)*4;if(src[p+3])src.copy(dst,(y*size+x)*4,p,p+4)}}
function segment(dst,src,a,b,c,d) {const sl=Math.hypot(b[0]-a[0],b[1]-a[1]),tl=Math.hypot(d[0]-c[0],d[1]-c[1]),su=[(b[0]-a[0])/sl,(b[1]-a[1])/sl],tu=[(d[0]-c[0])/tl,(d[1]-c[1])/tl];paint(dst,src,(x,y)=>{const px=x-c[0],py=y-c[1],along=(px*tu[0]+py*tu[1])*sl/tl,across=-px*tu[1]+py*tu[0];return[a[0]+su[0]*along-su[1]*across,a[1]+su[1]*along+su[0]*across]})}
function rotate(dst,src,anchor,target,angle) {const c=Math.cos(angle),s=Math.sin(angle);paint(dst,src,(x,y)=>[anchor[0]+c*(x-target[0])+s*(y-target[1]),anchor[1]-s*(x-target[0])+c*(y-target[1])])}
function over(dst,src,w=96,h=96,x0=0,y0=0) {for(let y=0;y<h;y++)for(let x=0;x<w;x++){const xx=x+x0,yy=y+y0,p=(y*w+x)*4;if(xx>=0&&xx<96&&yy>=0&&yy<96&&src[p+3])src.copy(dst,(yy*96+xx)*4,p,p+4)}}
function ink(b,top=0,bottom=95,protectedPixels=null) {for(let y=top;y<=bottom;y++)for(let x=0;x<96;x++){const p=(y*96+x)*4,rgb=b.subarray(p,p+3).toString('hex');if(!b[p+3]||protectedPixels?.[p+3]||['15141b','242633','392b29'].includes(rgb))continue;if([[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=96||y+dy<0||y+dy>=96||!b[((y+dy)*96+x+dx)*4+3]))b.set([21,20,27],p)}}
function hipInk(b,rig,drop,weapon) {if(!rig.hipOutline)return;for(let y=55+drop;y<=62+drop;y++)for(let x=0;x<96;x++){const p=(y*96+x)*4;if(!navy.includes(b.subarray(p,p+3).toString('hex'))||!b[p+3]||weapon?.[p+3])continue;if([[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=96||!b[((y+dy)*96+x+dx)*4+3]))b.set([21,20,27],p)}}
function padded(atlas,frame) {const b=Buffer.alloc(96*96*4);for(let y=0;y<80;y++){const p=((Math.floor(frame/4)*80+y)*320+frame%4*80)*4;atlas.copy(b,((y+8)*96+8)*4,p,p+320)}return b}
function direction(v,angle=0) {const n=Math.hypot(v[0],v[1]*.6),x=v[0]/n,y=v[1]*.6/n,c=Math.cos(angle),s=Math.sin(angle);return[x*c-y*s,x*s+y*c]}
function solve(model,grip,dir) {const palm=Math.hypot(model.hand.grip[0]-model.hand.anchor[0],model.hand.grip[1]-model.hand.anchor[1]),shoulder=model.shoulder,l1=Math.hypot(model.upper.b[0]-model.upper.a[0],model.upper.b[1]-model.upper.a[1]),l2=Math.hypot(model.fore.b[0]-model.fore.a[0],model.fore.b[1]-model.fore.a[1]);let wrist=[grip[0]-dir[0]*palm,grip[1]-dir[1]*palm],dx=wrist[0]-shoulder[0],dy=wrist[1]-shoulder[1],distance=Math.hypot(dx,dy),d=Math.min((l1+l2)*.98,Math.max(Math.abs(l1-l2)+.1,distance));if(distance<.001){dx=1;dy=0;distance=1}wrist=[shoulder[0]+dx/distance*d,shoulder[1]+dy/distance*d];const a=Math.atan2(dy,dx)+Math.acos(Math.max(-1,Math.min(1,(l1*l1+d*d-l2*l2)/(2*l1*d))));return{elbow:[shoulder[0]+l1*Math.cos(a),shoulder[1]+l1*Math.sin(a)],wrist,grip:[wrist[0]+dir[0]*palm,wrist[1]+dir[1]*palm],handAngle:Math.atan2(dir[1],dir[0])-Math.atan2(model.hand.grip[1]-model.hand.anchor[1],model.hand.grip[0]-model.hand.anchor[0])}}
function poseFor(model,rig,index) {const d=direction(rig.worldFacing),s=model.shoulder,side=s[0]>=40?1:-1;let grip,dir;
  if(index===0){grip=[s[0]+side*6,s[1]-4];dir=direction(rig.worldFacing,Math.PI)}
  else if(index===1){grip=[s[0]+side*6,s[1]-12];dir=direction(rig.worldFacing,-Math.PI/2)}
  else if(index===2){grip=[s[0]+d[0]*18,s[1]+d[1]*13+3];dir=d}
  else if(index===3){grip=model.followGrip||[s[0]+d[0]*9,s[1]+d[1]*7+8];dir=direction(rig.worldFacing,50*Math.PI/180)}
  else{grip=[model.grip[0]-d[0]*2,model.grip[1]-3];dir=[.08,Math.sqrt(1-.08*.08)]}
  return {...solve(model,grip,dir),dir,behind:model.far||index<2}
}
async function png(b,w,h,file,scale=1) {await sharp(b,{raw:{width:w,height:h,channels:4}}).resize(w*scale,h*scale,{kernel:'nearest'}).png().toFile(file)}
function atlas(cells,cols) {const width=cols*96,height=Math.ceil(cells.length/cols)*96,b=Buffer.alloc(width*height*4);for(let f=0;f<cells.length;f++)for(let y=0;y<96;y++)cells[f].copy(b,((Math.floor(f/cols)*96+y)*width+f%cols*96)*4,y*384,(y+1)*384);return{b,width,height}}
async function build(facing,dest) {
  const model=settings[facing],rig=rigs[facing],slug=facing.replaceAll('_','-'),[left,top,width,height]=rig.sourceCell;
  const src=await sharp(path.join(__dirname,'style-studies/eight-direction-consistency/turnaround-idle-64-v3.png')).extract({left,top,width,height}).ensureAlpha().raw().toBuffer(),r1=await sharp(path.join(root,`game/assets/player/r1-consistent-${slug}-20261105.png`)).ensureAlpha().raw().toBuffer();
  const bodyRaw=await sharp(path.join(__dirname,'consistent-parts',slug,'body.png')).ensureAlpha().raw().toBuffer();
  const parts={upper:cut(src,model.upper.mask,navy,model.repairMaterial),fore:cut(src,model.fore.mask,cuff,model.repairMaterial),hand:cut(src,model.hand.mask,skin)},legParts={};
  // Wood highlights share skin colors in the approved art; geometry owns the full bat.
  const originalBat=cut(src,rig.batMask,null),donorFacing=rig.batSourceFacing||facing,donorRig=rigs[donorFacing];
  // Removal-only coverage for source outlines outside the legacy bat mask.
  if(model.oldBatExtras){const extra=cut(src,model.oldBatExtras,null);for(let p=0;p<src.length;p+=4)if(extra[p+3])extra.copy(originalBat,p,p,p+4)}
  const [donorLeft,donorTop,donorWidth,donorHeight]=donorRig.sourceCell;
  const donorSource=donorFacing===facing?src:await sharp(path.join(__dirname,'style-studies/eight-direction-consistency/turnaround-idle-64-v3.png')).extract({left:donorLeft,top:donorTop,width:donorWidth,height:donorHeight}).ensureAlpha().raw().toBuffer();
  const bat=cut(donorSource,donorRig.batMask,null);
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
  const idle=padded(r1,8),staticBody=Buffer.from(idle);for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4,q=((y+8)*96+x+8)*4,isBat=oldWeapon[q+3];if(armMask[p+3]||isBat){if(armMask[p+3]&&core(x,y))staticBody.set([50,54,72,255],q);else if(y>=Math.min(rig.legs.right.hip[1],rig.legs.left.hip[1]))restingLegs.copy(staticBody,q,q,q+4);else staticBody.fill(0,q,q+4)}}
  const stationary=[],moving=[],poses=[];
  for(let a=0;a<6;a++){
    if(a===5){stationary.push(idle);for(let w=0;w<8;w++)moving.push(padded(r1,w));continue}
    const pose=poseFor(model,rig,a),arm=Buffer.alloc(96*96*4),weapon=Buffer.alloc(arm.length);poses.push(pose);
    segment(arm,parts.upper,model.upper.a,model.upper.b,model.shoulder,pose.elbow);segment(arm,parts.fore,model.fore.a,model.fore.b,pose.elbow,pose.wrist);rotate(arm,parts.hand,model.hand.anchor,pose.wrist,pose.handAngle);ink(arm);
    const end=[pose.grip[0]+pose.dir[0]*model.length,pose.grip[1]+pose.dir[1]*model.length];segment(weapon,bat,pivot,axisEnd,pose.grip,end);ink(weapon);
    const stand=Buffer.alloc(96*96*4);if(pose.behind){over(stand,weapon);over(stand,arm);over(stand,staticBody)}else{over(stand,staticBody);over(stand,arm);over(stand,weapon)}over(stand,headCell);over(stand,gearCell);hipInk(stand,rig,0,weapon);stationary.push(stand);
    for(let w=0;w<8;w++){const b=Buffer.alloc(96*96*4),drop=walk.bodyDrop[w],band=hipBand?hipBand.map(y=>y+drop):null;if(pose.behind)over(b,weapon,96,96,0,drop);for(const side of[far,rig.nearLeg])over(b,drawLeg(rig,legParts,side,joints(rig,rig.legs[side],w),band),80,80,8,8);if(pose.behind)over(b,arm,96,96,0,drop);over(b,upperCell,96,96,0,drop);if(!pose.behind){over(b,arm,96,96,0,drop);over(b,weapon,96,96,0,drop)}over(b,headCell,96,96,0,drop);over(b,gearCell,96,96,0,drop);const protectedWeapon=Buffer.alloc(b.length);over(protectedWeapon,weapon,96,96,0,drop);hipInk(b,rig,drop,protectedWeapon);moving.push(b)}
  }
  const standAtlas=atlas(stationary,3),walkAtlas=atlas(moving,8),image=`r2c8-attack-${slug}-20261106.png`,walkImage=`r2c8-attack-walk-${slug}-20261106.png`;await png(standAtlas.b,288,192,path.join(dest,image));await png(walkAtlas.b,768,576,path.join(dest,walkImage));
  const common={facing,cell_size:[96,96],scale:2,reference_height:64};
  return{facing,stationary,moving,poses,attack:{...common,image,canvas_size:[288,192],frames:names.map((name,a)=>({name,label:labels[a],start:times[a],end:times[a+1],clip_topleft:[a%3*96,Math.floor(a/3)*96,96,96],foot_pivot_topleft:[a%3*96+48,Math.floor(a/3)*96+80]}))},attack_walk:{...common,image:walkImage,canvas_size:[768,576],attack_steps:6,walk_phases:8,frames:moving.map((_,i)=>({name:`${names[Math.floor(i/8)]}_walk${i%8+1}`,attack_index:Math.floor(i/8),walk_frame_index:i%8+1,clip_topleft:[i%8*96,Math.floor(i/8)*96,96,96],foot_pivot_topleft:[i%8*96+48,Math.floor(i/8)*96+80]}))}}
}
async function sheet(cells,cols,rows,file) {const s=atlas(cells,cols),margin=80,width=s.width+margin,b=Buffer.alloc(width*s.height*4);for(let p=0;p<b.length;p+=4)b.set([49,63,75,255],p);for(let y=0;y<s.height;y++)for(let x=0;x<s.width;x++){const p=(y*s.width+x)*4;if(s.b[p+3])s.b.copy(b,(y*width+x+margin)*4,p,p+4)}const text=`<svg width="${width}" height="${s.height}">${rows.map((r,i)=>`<text x="2" y="${i*96+48}" font-size="10" font-family="monospace" fill="#e7ece7">${r}</text>`).join('')}</svg>`,base=await sharp(b,{raw:{width,height:s.height,channels:4}}).composite([{input:Buffer.from(text)}]).png().toBuffer();await sharp(base).resize(width*2,s.height*2,{kernel:'nearest'}).png().toFile(file)}
async function main() {const dest=path.join(root,'game/assets/combat'),review=path.join(root,'output/review/R2-C8-art');await fs.mkdir(review,{recursive:true});const metaPath=path.join(dest,'r2a-combat-20261106.json'),metadata=JSON.parse(await fs.readFile(metaPath,'utf8')),results=[];for(const facing of Object.keys(settings)){const r=await build(facing,dest);metadata['attack_'+facing]=r.attack;metadata['attack_walk_'+facing]=r.attack_walk;results.push(r);console.log(facing+': 6 + 48 poses saved')}await fs.writeFile(metaPath,JSON.stringify(metadata,null,2)+'\n');await sheet(results.flatMap(r=>r.stationary),6,results.map(r=>r.facing),path.join(review,'stationary-seven-directions-2x.png'));await sheet(results.flatMap(r=>r.moving.slice(16,24)),8,results.map(r=>r.facing),path.join(review,'hit-walk-seven-directions-2x.png'));await fs.writeFile(path.join(review,'pose-joints.json'),JSON.stringify(Object.fromEntries(results.map(r=>[r.facing,r.poses])),null,2)+'\n');console.log(JSON.stringify({sources:14,poses:378,review}))}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1})
