const sharp=require('sharp'),path=require('path');
(async()=>{
const {data:base,info}=await sharp(path.join(__dirname,'turnaround-v2.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
const original=Buffer.from(base),{data:edit,info:ei}=await sharp(path.join(__dirname,'right-v3-edit.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
if(ei.width!==384||ei.height!==512)throw Error('Expected one384x512 right-view edit');
for(let y=0;y<512;y++)edit.copy(base,(y*1536+768)*4,y*384*4,(y+1)*384*4);
for(let y=0;y<1024;y++)for(let x=0;x<1536;x++)if(!(y<512&&x>=768&&x<1152)){
const i=(y*1536+x)*4;if(!base.subarray(i,i+4).equals(original.subarray(i,i+4)))throw Error('Other seven views changed');
}
await sharp(base,{raw:info}).png().toFile(path.join(__dirname,'turnaround-v3.png'));
console.log('Corrected right view assembled; other seven raw RGBA views unchanged');
})().catch(e=>{console.error(e);process.exitCode=1});
