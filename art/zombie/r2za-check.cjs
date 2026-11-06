// Read-only production QA; deterministic reproduction goes to an ignored directory.
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),sharp=require('sharp')
const {createHash}=require('node:crypto'),{execFileSync}=require('node:child_process')
const r=require('./raster.cjs'),builder=require('./r2za-zombie-attack.cjs'),settings=require('./r2za-rigs.json')
const root=path.resolve(__dirname,'../..'),baseline='450f3a1',review=path.join(root,'output/review/R2-ZA-art'),times=[0,.08,.16,.30,.40,.52,.64,.72,.80]
const hash=b=>createHash('sha256').update(b).digest('hex')
function cell(data,width,[x,y,w,h]){const b=Buffer.alloc(w*h*4);for(let row=0;row<h;row++)data.copy(b,row*w*4,((y+row)*width+x)*4,((y+row)*width+x+w)*4);return b}
function components(b){
  const seen=new Uint8Array(6400),sizes=[]
  for(let p=0;p<6400;p++)if(!seen[p]&&b[p*4+3]){const queue=[p];seen[p]=1;let size=0;while(queue.length){const n=queue.pop(),x=n%80,y=Math.floor(n/80);size++;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const xx=x+dx,yy=y+dy,k=yy*80+xx;if(xx>=0&&xx<80&&yy>=0&&yy<80&&!seen[k]&&b[k*4+3]){seen[k]=1;queue.push(k)}}}sizes.push(size)}
  return sizes
}
function exactMask(frame,b){
  const mask=new Uint8Array(6400)
  for(const[yText,spans]of Object.entries(frame.opaque_rows)){
    const y=Number(yText);assert(Number.isInteger(y)&&y>=0&&y<80);let previous=-2
    for(const[left,right]of spans){assert(Number.isInteger(left)&&Number.isInteger(right)&&left>=0&&left<=right&&right<80&&left>previous+1);for(let x=left;x<=right;x++)mask[y*80+x]=1;previous=right}
  }
  for(let p=0;p<6400;p++)assert.equal(mask[p],Number(Boolean(b[p*4+3])),'exact alpha picking mask')
}
function touching(a,b,[x,y]){
  for(let yy=Math.max(0,Math.floor(y-5));yy<=Math.min(79,Math.ceil(y+5));yy++)for(let xx=Math.max(0,Math.floor(x-5));xx<=Math.min(79,Math.ceil(x+5));xx++){
    if(!a[(yy*80+xx)*4+3])continue
    for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const nx=xx+dx,ny=yy+dy;if(nx>=0&&nx<80&&ny>=0&&ny<80&&b[(ny*80+nx)*4+3])return true}
  }
  return false
}
async function main(){
  const pngPath=path.join(root,'game/assets/zombie/r2za-zombie-attack-20261106.png'),jsonPath=pngPath.replace('.png','.json'),[png,json]=await Promise.all([fs.readFile(pngPath),fs.readFile(jsonPath)]),metadata=JSON.parse(json),image=await sharp(png).ensureAlpha().raw().toBuffer({resolveWithObject:true})
  assert.equal(image.info.width,640);assert.equal(image.info.height,640)
  assert.deepEqual(Object.keys(metadata).sort(),['image','canvas_size','cell_size','scale','reference_height','facings'].sort())
  assert.equal(metadata.image,path.basename(pngPath));assert.deepEqual(metadata.canvas_size,[640,640]);assert.deepEqual(metadata.cell_size,[80,80]);assert.equal(metadata.scale,2);assert.equal(metadata.reference_height,64);assert.deepEqual(Object.keys(metadata.facings),r.facings)
  const frozenPaths=['art/zombie','art/player','game/assets/player','game/assets/combat','game/assets/zombie/r2z-zombie-20261106.png','game/assets/zombie/r2z-zombie-20261106.json','game/core.py','game/locomotion.py','game/player_visual.py']
  const frozen=new Set(execFileSync('git',['ls-tree','-r','--name-only',baseline,'--',...frozenPaths],{cwd:root}).toString().trim().split(/\r?\n/)),changed=execFileSync('git',['diff','--name-only',baseline],{cwd:root}).toString().trim().split(/\r?\n/)
  assert.deepEqual(changed.filter(f=>frozen.has(f)),[],'all previous zombie/player inputs and protected production files unchanged')
  const palette=new Set(JSON.parse(await fs.readFile(path.join(__dirname,'palette.json'),'utf8'))),oldMeta=JSON.parse(await fs.readFile(path.join(root,'game/assets/zombie/r2z-zombie-20261106.json'),'utf8')),oldPixels=await sharp(path.join(root,'game/assets/zombie',oldMeta.image)).ensureAlpha().raw().toBuffer()
  const atlas=await builder.makeAtlas();assert(atlas.pixels.equals(image.data),'current factory exactly reproduces frozen pixels');assert.deepEqual(atlas.metadata,metadata,'current factory metadata values')
  const report={baseline,frames:0,maskPixels:0,colors:0,alphaErrors:0,edgePixels:0,smallComponents:0,disconnectedStates:0,fixedLowerRows:0,idleReturns:0,bodyOutsideMaskChanges:0,baseHeadPixels:0,restoredPantPixels:0,boneChecks:0,tipAnchorChecks:0,jointContacts:0,jointExceptions:[],frozenFiles:frozen.size,unique:{}}
  const colors=new Set()
  for(const[col,facing]of r.facings.entries()){
    const result=atlas.results[col],config=settings[facing],frames=metadata.facings[facing],hashes=[]
    assert.equal(frames.length,8)
    const idle=cell(oldPixels,640,oldMeta.facings[facing].idle.clip_topleft)
    assert(result.source.equals(idle),'source matches approved production idle')
    for(let p=0;p<6400;p++){
      const q=p*4,x=p%80,y=Math.floor(p/80)
      if(y<=26&&result.source[q+3]){assert(result.base.subarray(q,q+4).equals(result.source.subarray(q,q+4)),`${facing} original head retained`);report.baseHeadPixels++}
      if(y>=config.waistY&&result.repaired[q+3]){
        const c=result.base.subarray(q,q+3).toString('hex'),edge=[[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=80||y+dy<0||y+dy>=80||!result.base[((y+dy)*80+x+dx)*4+3])
        assert(['353139','2b282b','312f3a'].includes(c)||(c==='15141b'&&edge),`${facing} restored trouser surface uses midtones`);report.restoredPantPixels++
      }
    }
    for(let phase=0;phase<8;phase++){
      const frame=frames[phase],b=cell(image.data,640,frame.clip_topleft)
      assert.deepEqual(frame.clip_topleft,[col*80,phase*80,80,80]);assert.deepEqual(frame.foot_pivot_topleft,[col*80+40,phase*80+72]);assert.equal(frame.start,times[phase]);assert.equal(frame.end,times[phase+1]);exactMask(frame,b)
      report.maskPixels+=6400;report.frames++;hashes.push(hash(b))
      assert(b.subarray(config.protectFromY*80*4).equals(idle.subarray(config.protectFromY*80*4)),`${facing}:${phase} fixed lower legs/soles`);report.fixedLowerRows++
      if(phase===7){assert(b.equals(idle),`${facing} final idle RGBA`);report.idleReturns++}
      const sizes=components(b);if(sizes.length!==1)report.disconnectedStates++;report.smallComponents+=sizes.filter(n=>n<=2).length
      for(let p=0;p<6400;p++){
        const x=p%80,y=Math.floor(p/80),q=p*4,alpha=b[q+3]
        if(alpha!==0&&alpha!==255)report.alphaErrors++
        if(alpha){const c=b.subarray(q,q+3).toString('hex');assert(palette.has(c),'approved zombie palette');colors.add(c);if(x===0||x===79||y===0||y===79)report.edgePixels++}
        if(!b.subarray(q,q+4).equals(idle.subarray(q,q+4))&&!result.removed[q+3]&&!result.layers[phase]?.right?.[q+3]&&!result.layers[phase]?.left?.[q+3])report.bodyOutsideMaskChanges++
      }
      if(phase===7)continue
      for(const[side,model]of Object.entries(config.arms)){
        const material=config.arms[model.textureFrom||side],pose=result.poses[phase][side],p=result.parts[side],upper=Buffer.alloc(25600),fore=Buffer.alloc(25600),hand=Buffer.alloc(25600)
        const expected=[Math.hypot(model.elbow[0]-model.shoulder[0],model.elbow[1]-model.shoulder[1]),Math.hypot(model.wrist[0]-model.elbow[0],model.wrist[1]-model.elbow[1])],actual=[Math.hypot(pose.elbow[0]-model.shoulder[0],pose.elbow[1]-model.shoulder[1]),Math.hypot(pose.wrist[0]-pose.elbow[0],pose.wrist[1]-pose.elbow[1])]
        for(let i=0;i<2;i++){assert(Math.abs(expected[i]-actual[i])<1e-8,'constant arm bone lengths');report.boneChecks++}
        const a=pose.handAngle*Math.PI/180,dx=material.tip[0]-material.wrist[0],dy=material.tip[1]-material.wrist[1]
        assert(Math.hypot(pose.tip[0]-pose.wrist[0]-Math.cos(a)*dx+Math.sin(a)*dy,pose.tip[1]-pose.wrist[1]-Math.sin(a)*dx-Math.cos(a)*dy)<1e-8,'same hand fingertip anchor');report.tipAnchorChecks++
        r.segment(upper,p.upper,material.shoulder,material.elbow,model.shoulder,pose.elbow);r.segment(fore,p.fore,material.elbow,material.wrist,pose.elbow,pose.wrist);r.rotate(hand,p.hand,material.wrist,pose.wrist,pose.handAngle)
        for(const[name,left,right,point]of [['elbow',upper,fore,pose.elbow],['wrist',fore,hand,pose.wrist]])if(touching(left,right,point))report.jointContacts++;else report.jointExceptions.push({facing,phase,side,joint:name})
      }
    }
    report.unique[facing]=new Set(hashes).size;assert.equal(report.unique[facing],8,`${facing} eight genuine attack poses`)
  }
  report.colors=colors.size;assert(report.colors<=24);assert.equal(report.frames,64);assert.equal(report.idleReturns,8);assert.equal(report.fixedLowerRows,64)
  for(const k of ['alphaErrors','edgePixels','smallComponents','disconnectedStates','bodyOutsideMaskChanges'])assert.equal(report[k],0,k)
  assert.deepEqual(report.jointExceptions,[],'opaque elbow/wrist contacts')
  const temporary=path.join(review,'reproduction');await r.png(atlas.pixels,640,640,path.join(temporary,metadata.image));await fs.writeFile(path.join(temporary,path.basename(jsonPath)),JSON.stringify(atlas.metadata,null,2)+'\n')
  assert((await fs.readFile(path.join(temporary,metadata.image))).equals(png),'reproduced PNG bytes');assert.deepEqual(JSON.parse(await fs.readFile(path.join(temporary,path.basename(jsonPath)),'utf8')),metadata,'reproduced JSON values, EOL independent')
  const imported=execFileSync(process.execPath,['-e',"require('./art/zombie/r2za-zombie-attack.cjs')"],{cwd:root});assert.equal(imported.length,0)
  assert((await fs.readFile(pngPath)).equals(png));assert((await fs.readFile(jsonPath)).equals(json));report.reproducedPngs=1;report.reproducedJsonValues=1;report.productWrites=0;report.importSideEffects=0
  await fs.writeFile(path.join(review,'asset-check.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report))
}
main().catch(error=>{console.error(error);process.exitCode=1})
