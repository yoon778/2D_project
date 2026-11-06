// One common isotropic scale, foot translations, and a shared hard-edge palette.
const fs=require('node:fs/promises'),path=require('node:path'),sharp=require('sharp'),raster=require('./raster.cjs')
const root=path.resolve(__dirname,'../..'),config=require('./r2z-source.json')
function palette(source,count) {
  const histogram=new Map()
  for(let p=0;p<source.length;p+=4)if(source[p+3]){const key=source.subarray(p,p+3).toString('hex');histogram.set(key,(histogram.get(key)||0)+1)}
  const points=[...histogram].map(([hex,n])=>({rgb:[0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)),n}))
  const describe=values=>{
    const weight=values.reduce((n,p)=>n+p.n,0),mean=[0,1,2].map(c=>values.reduce((n,p)=>n+p.n*p.rgb[c],0)/weight),variance=[0,1,2].map(c=>values.reduce((n,p)=>n+p.n*(p.rgb[c]-mean[c])**2,0)/weight)
    return{values,weight,mean,variance,score:Math.max(...variance)*Math.sqrt(weight)}
  }
  const cubes=[describe(points)]
  while(cubes.length<count){
    let chosen=-1
    for(let i=0;i<cubes.length;i++)if(cubes[i].values.length>1&&(chosen<0||cubes[i].score>cubes[chosen].score))chosen=i
    if(chosen<0)break
    const cube=cubes.splice(chosen,1)[0],axis=cube.variance.indexOf(Math.max(...cube.variance)),sorted=cube.values.sort((a,b)=>a.rgb[axis]-b.rgb[axis]);let weight=0,split=0
    while(split<sorted.length-1&&weight<cube.weight/2)weight+=sorted[split++].n
    cubes.push(describe(sorted.slice(0,split)),describe(sorted.slice(split)))
  }
  return cubes.map(c=>c.mean.map(Math.round))
}
async function normalize() {
  const {data,info}=await sharp(path.join(__dirname,config.source)).ensureAlpha().raw().toBuffer({resolveWithObject:true}),native=Buffer.alloc(320*160*4)
  for(const [i,name]of raster.facings.entries()){
    const rig=config.facings[name],[x0,y0,x1,y1]=rig.sourceBounds,[fx,fy]=rig.sourceFoot
    for(let y=0;y<80;y++)for(let x=0;x<80;x++){
      const sx=Math.round(fx+(x-40)/config.nativeScale),sy=Math.round(fy+(y-72)/config.nativeScale)
      if(sx<x0||sx>x1||sy<y0||sy>y1)continue
      const from=(sy*info.width+sx)*4,to=((Math.floor(i/4)*80+y)*320+i%4*80+x)*4
      if(data[from+3]>=config.alphaThreshold){data.copy(native,to,from,from+3);native[to+3]=255}
    }
  }
  const colors=palette(native,23),cache=new Map()
  for(let p=0;p<native.length;p+=4)if(native[p+3]){
    const key=native.subarray(p,p+3).toString('hex')
    if(!cache.has(key)){let best=Infinity,selected;for(const rgb of colors){const d=3*(native[p]-rgb[0])**2+4*(native[p+1]-rgb[1])**2+2*(native[p+2]-rgb[2])**2;if(d<best){best=d;selected=rgb}}cache.set(key,selected)}
    native.set(cache.get(key),p)
  }
  for(let i=0;i<8;i++){
    const b=Buffer.alloc(80*80*4)
    for(let y=0;y<80;y++){const p=((Math.floor(i/4)*80+y)*320+i%4*80)*4;native.copy(b,y*320,p,p+320)}
    raster.outline(b,config.outline)
    for(let y=0;y<80;y++)b.copy(native,((Math.floor(i/4)*80+y)*320+i%4*80)*4,y*320,(y+1)*320)
  }
  return{pixels:native,info}
}
async function main() {
  const {pixels:native,info}=await normalize()
  await raster.png(native,320,160,path.join(__dirname,'zombie-idle-native-20261106.png'))
  const review=path.join(root,'output/review/R2-Z-art')
  await raster.png(native,320,160,path.join(review,'zombie-idle-eight-4x.png'),4)
  const player=await sharp(path.join(root,'art/player/style-studies/eight-direction-consistency/turnaround-idle-64-v3.png')).ensureAlpha().raw().toBuffer(),comparison=Buffer.alloc(640*160*4)
  for(let i=0;i<8;i++)for(let y=0;y<80;y++){
    const p=((Math.floor(i/4)*80+y)*320+i%4*80)*4
    player.copy(comparison,(y*640+i*80)*4,p,p+320)
    native.copy(comparison,((80+y)*640+i*80)*4,p,p+320)
  }
  await raster.png(comparison,640,160,path.join(review,'player-zombie-comparison-3x.png'),3)
  const actual=new Set()
  for(let p=0;p<native.length;p+=4)if(native[p+3])actual.add(native.subarray(p,p+3).toString('hex'))
  await fs.writeFile(path.join(__dirname,'palette.json'),JSON.stringify([...actual],null,2)+'\n')
  console.log(JSON.stringify({source:[info.width,info.height],commonScale:config.nativeScale,colors:actual.size,output:'art/zombie/zombie-idle-native-20261106.png'}))
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1})
module.exports={palette,normalize}
