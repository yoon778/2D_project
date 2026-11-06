// Product resources stay read-only; reproduction writes only ignored review files.
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),sharp=require('sharp')
const {createHash}=require('node:crypto'),{execFileSync}=require('node:child_process')
const r=require('./raster.cjs'),rig=require('./r2z-rig.json'),sourceConfig=require('./r2z-source.json'),walk=require('../player/consistent-rig.json')
const root=path.resolve(__dirname,'../..'),baseline='e85cc07',review=path.join(root,'output/review/R2-Z-art')
const hash=b=>createHash('sha256').update(b).digest('hex')
function cell(data,width,clip){const[x,y,w,h]=clip,b=Buffer.alloc(w*h*4);for(let row=0;row<h;row++)data.copy(b,row*w*4,((y+row)*width+x)*4,((y+row)*width+x+w)*4);return b}
function components(b){
  const seen=new Uint8Array(6400),sizes=[]
  for(let p=0;p<6400;p++)if(!seen[p]&&b[p*4+3]){
    const queue=[p];let count=0;seen[p]=1
    while(queue.length){const n=queue.pop(),x=n%80,y=Math.floor(n/80);count++;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const xx=x+dx,yy=y+dy,next=yy*80+xx;if(xx>=0&&xx<80&&yy>=0&&yy<80&&!seen[next]&&b[next*4+3]){seen[next]=1;queue.push(next)}}}
    sizes.push(count)
  }
  return sizes
}
function box(b){let x0=80,y0=80,x1=-1,y1=-1,n=0;for(let y=0;y<80;y++)for(let x=0;x<80;x++)if(b[(y*80+x)*4+3]){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);n++}return{bbox:[x0,y0,x1,y1],width:x1-x0+1,height:y1-y0+1,pixels:n}}
function checkMask(frame,b){
  const mask=new Uint8Array(6400)
  for(const[yText,spans]of Object.entries(frame.opaque_rows)){
    const y=Number(yText);assert(Number.isInteger(y)&&y>=0&&y<80);let previous=-2
    for(const[left,right]of spans){assert(Number.isInteger(left)&&Number.isInteger(right)&&left>=0&&left<=right&&right<80&&left>previous+1);for(let x=left;x<=right;x++)mask[y*80+x]=1;previous=right}
  }
  for(let p=0;p<6400;p++)assert.equal(mask[p],Number(Boolean(b[p*4+3])),'opaque_rows must match every source alpha pixel')
}
async function main(){
  const pngFile=path.join(root,'game/assets/zombie/r2z-zombie-20261106.png'),jsonFile=pngFile.replace('.png','.json'),nativeFile=path.join(__dirname,rig.master),sourceFile=path.join(__dirname,sourceConfig.source)
  const [png,json,nativePng,input]=await Promise.all([fs.readFile(pngFile),fs.readFile(jsonFile),fs.readFile(nativeFile),fs.readFile(sourceFile)]),metadata=JSON.parse(json)
  const image=await sharp(png).ensureAlpha().raw().toBuffer({resolveWithObject:true}),native=await sharp(nativePng).ensureAlpha().raw().toBuffer()
  assert.equal(image.info.width,640);assert.equal(image.info.height,1120)
  assert.equal(metadata.image,path.basename(pngFile));assert.deepEqual(metadata.canvas_size,[640,1120]);assert.deepEqual(metadata.cell_size,[80,80]);assert.equal(metadata.scale,2);assert.equal(metadata.reference_height,64);assert.equal(metadata.stride_distance,64)
  assert.deepEqual(Object.keys(metadata.facings),r.facings);assert.deepEqual(Object.keys(metadata.frames),['dead'])
  assert.equal(sourceConfig.nativeScale,5/28)
  for(const config of Object.values(sourceConfig.facings))assert.deepEqual(Object.keys(config).sort(),['sourceBounds','sourceCell','sourceFoot'].sort(),'only foot translation varies by view')
  const frozen=['art/player','game/assets/player','game/assets/combat','game/core.py','game/combat.py','game/locomotion.py','game/player_visual.py']
  assert.equal(execFileSync('git',['diff','--name-only',baseline,'--',...frozen],{cwd:root}).toString().trim(),'','frozen player/combat resources and production rules')
  const report={baseline,states:0,maskPixels:0,palette:[],alphaErrors:0,edgePixels:0,smallComponents:0,disconnectedStates:0,idleSourceMatches:0,hitIdleReturns:0,fixedFootFrames:0,outlinedLowerEdges:0,bodyPixelsPreserved:0,unusedCells:7,idle:{},walkHeights:{},hitHeights:{},unique:{},sourceSha256:hash(input)}
  const colors=new Set(),descriptors=[],idleHashes=[]
  for(const[col,facing]of r.facings.entries()){
    const state=metadata.facings[facing],idle=cell(image.data,640,state.idle.clip_topleft),[left,top]=sourceConfig.facings[facing].sourceCell,original=cell(native,320,[left,top,80,80])
    assert(idle.equals(original),`${facing} supplied native idle`);report.idleSourceMatches++;idleHashes.push(hash(idle));report.idle[facing]=box(idle)
    assert.equal(state.walk.length,8);assert.equal(state.hit.length,4)
    const walkHashes=[],hitHashes=[],walkHeights=[],hitHeights=[],body=await sharp(path.join(__dirname,'parts',facing.replaceAll('_','-'),'body.png')).ensureAlpha().raw().toBuffer()
    descriptors.push({facing,type:'idle',index:0,col,row:0,frame:state.idle})
    for(const[i,frame]of state.walk.entries()){
      const b=cell(image.data,640,frame.clip_topleft),drop=walk.bodyDrop[i],alpha=(x,y)=>x>=0&&x<80&&y>=0&&y<80&&b[(y*80+x)*4+3]
      walkHashes.push(hash(b));walkHeights.push(box(b).height);descriptors.push({facing,type:'walk',index:i,col,row:1+i,frame})
      for(let y=0;y<80-drop;y++)for(let x=0;x<80;x++){
        const p=(y*80+x)*4,q=((y+drop)*80+x)*4
        if(body[p+3]){assert(b.subarray(q,q+4).equals(body.subarray(p,p+4)),`${facing}:${i} unchanged upper body`);report.bodyPixelsPreserved++}
      }
      // Keep the pelvis join open; exposed legs below it retain a dark contour.
      for(let y=rig.facings[facing].hipY+3+drop;y<80;y++)for(let x=0;x<80;x++){
        const p=(y*80+x)*4,source=((y-drop)*80+x)*4
        if(!alpha(x,y)||body[source+3]||![[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>!alpha(x+dx,y+dy)))continue
        assert.equal(b.subarray(p,p+3).toString('hex'),rig.outline,`${facing}:${i} lower-leg contour`);report.outlinedLowerEdges++
      }
    }
    for(const[i,frame]of state.hit.entries()){
      assert.equal(frame.start,r.hitTimes[i]);assert.equal(frame.end,r.hitTimes[i+1])
      const b=cell(image.data,640,frame.clip_topleft);hitHashes.push(hash(b));hitHeights.push(box(b).height);descriptors.push({facing,type:'hit',index:i,col,row:9+i,frame})
      assert(b.subarray(66*80*4).equals(idle.subarray(66*80*4)),`${facing}:${i} unchanged boots/soles`);report.fixedFootFrames++
      if(i===3){assert(b.equals(idle),`${facing} final hit equals idle`);report.hitIdleReturns++}
    }
    assert.equal(new Set(walkHashes).size,8,`${facing} unique walk8`);assert.equal(new Set(hitHashes).size,4,`${facing} unique hit4`)
    report.unique[facing]={walk:8,hit:4};report.walkHeights[facing]=[Math.min(...walkHeights),Math.max(...walkHeights)];report.hitHeights[facing]=[Math.min(...hitHeights),Math.max(...hitHeights)]
  }
  assert.equal(new Set(idleHashes).size,8)
  descriptors.push({facing:'dead',type:'dead',index:0,col:0,row:13,frame:metadata.frames.dead})
  for(const d of descriptors){
    const {frame,col,row}=d;assert.deepEqual(frame.clip_topleft,[col*80,row*80,80,80]);assert.deepEqual(frame.foot_pivot_topleft,[col*80+40,row*80+72])
    const b=cell(image.data,640,frame.clip_topleft);checkMask(frame,b);report.maskPixels+=6400;report.states++
    const groups=components(b);if(groups.length!==1)report.disconnectedStates++;report.smallComponents+=groups.filter(n=>n<=2).length
    for(let y=0;y<80;y++)for(let x=0;x<80;x++){const p=(y*80+x)*4;if(b[p+3]!==0&&b[p+3]!==255)report.alphaErrors++;if(b[p+3]){colors.add(b.subarray(p,p+3).toString('hex'));if(x===0||y===0||x===79||y===79)report.edgePixels++}}
    if(d.type==='dead')report.dead=box(b)
  }
  for(let col=1;col<8;col++)assert(cell(image.data,640,[col*80,1040,80,80]).equals(Buffer.alloc(80*80*4)),'unused corpse row cells transparent')
  report.palette=[...colors];assert(colors.size<=24);assert.equal(report.states,105)
  for(const k of ['alphaErrors','edgePixels','smallComponents','disconnectedStates'])assert.equal(report[k],0,k)
  const output=execFileSync(process.execPath,['-e',"require('./art/zombie/prepare-native.cjs');require('./art/zombie/r2z-zombie-assets.cjs')"],{cwd:root});assert.equal(output.length,0,'imports must not bake')
  const normalized=await require('./prepare-native.cjs').normalize();assert(normalized.pixels.equals(native),'same common-scale normalization')
  const builder=require('./r2z-zombie-assets.cjs'),states={}
  for(const facing of r.facings){const[left,top]=sourceConfig.facings[facing].sourceCell;states[facing]=await builder.build(facing,cell(normalized.pixels,320,[left,top,80,80]),{writeParts:false})}
  const temporary=path.join(review,'reproduction');await r.writeAssets(states,builder.corpse(states.front_right),temporary);await r.png(normalized.pixels,320,160,path.join(temporary,'idle-native.png'))
  assert((await fs.readFile(path.join(temporary,metadata.image))).equals(png),'reproduced atlas PNG bytes');assert.deepEqual(JSON.parse(await fs.readFile(path.join(temporary,path.basename(jsonFile)),'utf8')),metadata,'reproduced metadata values');assert((await fs.readFile(path.join(temporary,'idle-native.png'))).equals(nativePng),'reproduced native master bytes')
  assert((await fs.readFile(pngFile)).equals(png));assert((await fs.readFile(jsonFile)).equals(json));assert((await fs.readFile(nativeFile)).equals(nativePng));assert.equal(hash(await fs.readFile(sourceFile)),report.sourceSha256)
  report.reproducedPngs=2;report.reproducedJsonValues=1;report.productWrites=0;report.importSideEffects=0
  await fs.writeFile(path.join(review,'asset-check.json'),JSON.stringify(report,null,2)+'\n')
  console.log(JSON.stringify(report))
}
main().catch(error=>{console.error(error);process.exitCode=1})
