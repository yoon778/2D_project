// Native 80px sprite assembly. Character masks/joints come from the supplied art.
const fs = require('node:fs/promises'), path = require('node:path'), sharp = require('sharp')
const size = 80, facings = ['front','front_right','right','back_right','back','back_left','left','front_left']
const hitTimes = [0,.06,.14,.26,.40]
function inside(x,y,p) {
  let hit=false
  for(let i=0,j=p.length-1;i<p.length;j=i++){const[a,b]=p[i],[c,d]=p[j];if((b>y)!==(d>y)&&x<(c-a)*(y-b)/(d-b)+a)hit=!hit}
  return hit
}
function contains(x,y,mask) {
  if(!mask)return false
  if(Array.isArray(mask))return inside(x+.5,y+.5,mask)
  if(mask.rows){const r=mask.rows[y];return Boolean(r&&(Array.isArray(r[0])?r:[r]).some(([a,b])=>x>=a&&x<=b))}
  return inside(x+.5,y+.5,mask.polygon)
}
function cut(source,mask) {
  const b=Buffer.alloc(source.length)
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const p=(y*size+x)*4
    if(contains(x,y,mask)&&(!mask.colors||mask.colors.includes(source.subarray(p,p+3).toString('hex'))))source.copy(b,p,p,p+4)
  }
  for(const patch of mask.copies||[]){
    const[sx,sy,w,h]=patch.source,[tx,ty]=patch.target
    for(let y=0;y<h;y++)for(let x=0;x<w;x++){
      const xx=tx+x,yy=ty+y,fx=sx+x,fy=sy+y
      if(xx<0||xx>=size||yy<0||yy>=size||fx<0||fx>=size||fy<0||fy>=size||!contains(xx,yy,{rows:mask.restoreRows}))continue
      const from=(fy*size+fx)*4,to=(yy*size+xx)*4
      if(!b[to+3]&&source[from+3]&&(!mask.colors||mask.colors.includes(source.subarray(from,from+3).toString('hex'))))source.copy(b,to,from,from+4)
    }
  }
  return b
}
function paint(target,source,inverse) {
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const[sx,sy]=inverse(x,y).map(Math.round)
    if(sx<0||sx>=size||sy<0||sy>=size)continue
    const p=(sy*size+sx)*4
    if(source[p+3])source.copy(target,(y*size+x)*4,p,p+4)
  }
}
function overlay(target,source,dx=0,dy=0) {paint(target,source,(x,y)=>[x-dx,y-dy])}
function segment(target,source,a,b,c,d) {
  const sl=Math.hypot(b[0]-a[0],b[1]-a[1]),tl=Math.hypot(d[0]-c[0],d[1]-c[1])
  if(sl<.01||tl<.01)throw new Error('Nonzero source and target bones required')
  const su=[(b[0]-a[0])/sl,(b[1]-a[1])/sl],tu=[(d[0]-c[0])/tl,(d[1]-c[1])/tl]
  paint(target,source,(x,y)=>{const px=x-c[0],py=y-c[1],along=(px*tu[0]+py*tu[1])*sl/tl,across=-px*tu[1]+py*tu[0];return[a[0]+su[0]*along-su[1]*across,a[1]+su[1]*along+su[0]*across]})
}
function rotate(target,source,anchor,targetAnchor,degrees) {
  const a=degrees*Math.PI/180,c=Math.cos(a),s=Math.sin(a)
  paint(target,source,(x,y)=>[anchor[0]+c*(x-targetAnchor[0])+s*(y-targetAnchor[1]),anchor[1]-s*(x-targetAnchor[0])+c*(y-targetAnchor[1])])
}
function outline(b,color,top=0) {
  const rgb=[0,2,4].map(i=>parseInt(color.slice(i,i+2),16))
  for(let y=top;y<size;y++)for(let x=0;x<size;x++){
    const p=(y*size+x)*4
    if(!b[p+3])continue
    if([[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx<0||x+dx>=size||y+dy<0||y+dy>=size||!b[((y+dy)*size+x+dx)*4+3]))b.set(rgb,p)
  }
}
function opaqueRows(b) {
  const rows={}
  for(let y=0;y<size;y++){
    const spans=[];let left=-1
    for(let x=0;x<=size;x++){
      const on=x<size&&b[(y*size+x)*4+3]
      if(on&&left<0)left=x
      if(!on&&left>=0){spans.push([left,x-1]);left=-1}
    }
    if(spans.length)rows[y]=spans
  }
  return rows
}
function atlas(states,dead) {
  const width=640,height=1120,pixels=Buffer.alloc(width*height*4)
  const metadata={image:'r2z-zombie-20261106.png',canvas_size:[width,height],cell_size:[size,size],scale:2,reference_height:64,stride_distance:64,facings:{},frames:{}}
  const put=(b,col,row)=>{
    if(b.length!==size*size*4)throw new Error('Expected an 80x80 RGBA cell')
    for(let y=0;y<size;y++)b.copy(pixels,((row*size+y)*width+col*size)*4,y*size*4,(y+1)*size*4)
    return{clip_topleft:[col*size,row*size,size,size],foot_pivot_topleft:[col*size+40,row*size+72],opaque_rows:opaqueRows(b)}
  }
  for(const [col,facing]of facings.entries()){
    const state=states[facing]
    if(!state||state.walk.length!==8||state.hit.length!==4)throw new Error(`Missing idle/walk8/hit4 for ${facing}`)
    metadata.facings[facing]={idle:put(state.idle,col,0),walk:state.walk.map((b,i)=>put(b,col,1+i)),hit:state.hit.map((b,i)=>({...put(b,col,9+i),start:hitTimes[i],end:hitTimes[i+1]}))}
  }
  metadata.frames.dead=put(dead,0,13)
  return{pixels,width,height,metadata}
}
async function png(pixels,width,height,file,scale=1) {
  await fs.mkdir(path.dirname(file),{recursive:true})
  await sharp(pixels,{raw:{width,height,channels:4}}).resize(width*scale,height*scale,{kernel:'nearest'}).png().toFile(file)
}
async function writeAssets(states,dead,directory) {
  const result=atlas(states,dead)
  await fs.mkdir(directory,{recursive:true})
  await png(result.pixels,result.width,result.height,path.join(directory,result.metadata.image))
  await fs.writeFile(path.join(directory,'r2z-zombie-20261106.json'),JSON.stringify(result.metadata,null,2)+'\n')
  return result
}
module.exports={size,facings,hitTimes,contains,cut,paint,overlay,segment,rotate,outline,opaqueRows,atlas,png,writeAssets}
