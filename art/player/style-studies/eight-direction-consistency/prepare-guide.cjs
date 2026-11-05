const sharp=require('sharp'),fs=require('fs'),path=require('path');
(async()=>{
const out=__dirname;
const labels=['FRONT','FRONT-RIGHT','RIGHT','BACK-RIGHT','BACK','BACK-LEFT','LEFT','FRONT-LEFT'];
let body='<rect width="1536" height="1024" fill="#24303b"/>';
for(let i=0;i<8;i++){
const x=i%4*384,y=Math.floor(i/4)*512;
body+='<rect x="'+x+'" y="'+y+'" width="384" height="512" fill="none" stroke="#647482" stroke-width="2"/><text x="'+(x+16)+'" y="'+(y+27)+'" fill="#ffffff" font-family="Arial" font-size="22">'+(i+1)+' '+labels[i]+'</text>';
for(const [name,yy,color] of [['HEAD',86,'#f8e098'],['EYES',160,'#86b7ca'],['SHOULDER',218,'#87939d'],['BELT',320,'#87939d'],['HIP',344,'#87939d'],['SOLE',464,'#89dfbd']]){
body+='<line x1="'+(x+20)+'" x2="'+(x+364)+'" y1="'+(y+yy)+'" y2="'+(y+yy)+'" stroke="'+color+'" stroke-width="2"/><text x="'+(x+8)+'" y="'+(y+yy-5)+'" fill="'+color+'" font-family="Arial" font-size="12">'+name+'</text>';
}
body+='<line x1="'+(x+192)+'" x2="'+(x+192)+'" y1="'+(y+40)+'" y2="'+(y+486)+'" stroke="#87939d" stroke-width="1"/>';
}
await sharp(Buffer.from('<svg width="1536" height="1024" xmlns="http://www.w3.org/2000/svg">'+body+'</svg>')).png().toFile(path.join(out,'turnaround-guides.png'));
await sharp(path.resolve(out,'../front-right-idle-64.png')).resize({height:512,kernel:'nearest'}).png().toFile(path.join(out,'approved-character-reference-8x.png'));
console.log('guide and approved reference ready');
})().catch(e=>{console.error(e);process.exitCode=1});
