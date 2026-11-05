const fs=require('node:fs'),path=require('node:path'),sharp=require('sharp');
const facings=['front','front_right','right','back_right','back','back_left','left','front_left'];
const bodyAnchors=require('./body-anchors.json');
const palette=require('../front-right-idle-64.json').palette_hex.map(h=>[0,2,4].map(i=>parseInt(h.slice(i,i+2),16)));
async function compile(){
const sheet=path.join(__dirname,'turnaround-v3.png');
const {data,info}=await sharp(sheet).ensureAlpha().raw().toBuffer({resolveWithObject:true});
if(info.width!==1536||info.height!==1024)throw Error('Expected1536x1024 control sheet');
for(let i=0;i<data.length;i+=4){
 if(data[i+3]<200){data.fill(0,i,i+4);continue}
 let best=palette[0],err=Infinity;
 for(const p of palette){const e=(data[i]-p[0])**2+(data[i+1]-p[1])**2+(data[i+2]-p[2])**2;if(e<err){err=e;best=p}}
 data.set([...best,255],i);
}
const cleaned=await sharp(data,{raw:info}).png().toBuffer(),tiles=[],report={status:'candidate_for_review',source:'turnaround-v3.png',common_source_pixels_per_native_pixel:6,per_direction_scaling:false,hard_alpha_threshold:200,palette_colors:24,facings:{}};
for(let n=0;n<8;n++){
 const {data:cell,info:ci}=await sharp(cleaned).extract({left:n%4*384,top:Math.floor(n/4)*512,width:384,height:480}).resize(64,80,{kernel:'nearest'}).raw().toBuffer({resolveWithObject:true});
 let sx=0,count=0;
 for(let y=55;y<=65;y++)for(let x=0;x<64;x++){let i=(y*64+x)*4;if(cell[i+3]&&cell[i+2]>cell[i]&&cell[i+2]>cell[i+1]){sx+=x;count++}}
 if(!count)throw Error('Missing lower-leg registration '+facings[n]);
 // Body boot anchors are reviewed separately: a bat tip must never determine ground registration.
 const sole=bodyAnchors.facings[facings[n]].body_boot_sole_native;
 const axis=Math.round(sx/count),dx=40-axis,dy=72-sole,out=Buffer.alloc(80*80*4);
 for(let y=0;y<80;y++)for(let x=0;x<64;x++){const xx=x+dx,yy=y+dy;if(xx>=0&&xx<80&&yy>=0&&yy<80)cell.copy(out,(yy*80+xx)*4,(y*64+x)*4,(y*64+x)*4+4);else if(cell[(y*64+x)*4+3])throw Error('Registration clips pose '+facings[n])}
 let minX=80,minY=80,maxX=-1,maxY=-1;const colors=new Set();
 for(let y=0;y<80;y++)for(let x=0;x<80;x++){const i=(y*80+x)*4;if(!out[i+3])continue;minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);colors.add(out.subarray(i,i+3).toString('hex'));}
 report.facings[facings[n]]={alpha_bounds:[minX,minY,maxX,maxY],silhouette_height_including_bat:maxY-minY+1,registration:[dx,dy],body_boot_sole_after_registration:sole+dy,body_anchors:bodyAnchors.facings[facings[n]],lower_leg_axis:axis,color_count:colors.size,body_height_measurement:'Manual body/boot anchors; alpha bounds also reported separately'};
 if(minX===0||maxX===79||minY===0||maxY===79)throw Error('Cell edge contact '+facings[n]);
 tiles.push({input:await sharp(out,{raw:{width:80,height:80,channels:4}}).png().toBuffer(),left:n%4*80,top:Math.floor(n/4)*80});
}
await sharp({create:{width:320,height:160,channels:4,background:'#00000000'}}).composite(tiles).png().toFile(path.join(__dirname,'turnaround-idle-64-v3.png'));
let guides='';
for(let n=0;n<8;n++){const x=n%4*80,y=Math.floor(n/4)*80;guides+='<line x1="'+x+'" x2="'+(x+80)+'" y1="'+(y+8)+'" y2="'+(y+8)+'" stroke="#65727c" stroke-width=".3"/><line x1="'+x+'" x2="'+(x+80)+'" y1="'+(y+73)+'" y2="'+(y+73)+'" stroke="#65727c" stroke-width=".3"/>';}
const preview=await sharp({create:{width:320,height:160,channels:4,background:'#313f4b'}}).composite([{input:Buffer.from('<svg width="320" height="160" xmlns="http://www.w3.org/2000/svg">'+guides+'</svg>'),left:0,top:0},...tiles]).png().toBuffer();
await sharp(preview).resize(1280,640,{kernel:'nearest'}).png().toFile(path.join(__dirname,'turnaround-preview-4x.png'));
fs.writeFileSync(path.join(__dirname,'turnaround-review.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report.facings));
}
compile().catch(e=>{console.error(e);process.exitCode=1});
