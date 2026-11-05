const fs=require('fs'),path=require('path'),sharp=require('sharp');
// Validate the actual baked PNG contour; optional arguments: source-directory report-path.
const root=path.resolve(__dirname,'../..'),art=__dirname,cfg=require(path.join(art,'consistent-rig.json'));
for(const file of ['consistent-front-back.json','consistent-side.json','consistent-diagonal.json'])Object.assign(cfg.facings,require(path.join(art,file)));
const dark=new Set(['15141b','242633','392b29']),dirs=[[1,0],[-1,0],[0,1],[0,-1]];
const sourceDir=path.resolve(root,process.argv[2]||'game/assets/player');
(async()=>{
const report={scope:'Exposed lower-leg alpha boundary, excluding fixed torso/bat and their one-pixel margin',dark_colors:[...dark],facings:{},exposed:0,missing:0};
for(const [facing,rig] of Object.entries(cfg.facings)){
const slug=facing.replaceAll('_','-'),{data:atlas}=await sharp(path.join(sourceDir,'r1-consistent-'+slug+'-20261105.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
const body=await sharp(path.join(art,'consistent-parts',slug,'body.png')).ensureAlpha().raw().toBuffer();
const bat=await sharp(path.join(art,'consistent-parts',slug,'bat.png')).ensureAlpha().raw().toBuffer();
const frames=[];
for(let f=0;f<8;f++){
 const x0=f%4*80,y0=Math.floor(f/4)*80,drop=cfg.bodyDrop[f],cutoff=Math.max(rig.legs.right.hip[1],rig.legs.left.hip[1])+3+drop;
 const at=(x,y)=>(y0+y)*320*4+(x0+x)*4,opaque=(x,y)=>x>=0&&x<80&&y>=0&&y<80&&atlas[at(x,y)+3];
 const ignored=(x,y)=>{for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const xx=x+dx,yy=y+dy-drop;if(xx>=0&&xx<80&&yy>=0&&yy<80&&(body[(yy*80+xx)*4+3]||bat[(yy*80+xx)*4+3]))return true}return false};
 let exposed=0,missing=0;const samples=[];
 for(let y=cutoff;y<79;y++)for(let x=1;x<79;x++){
 if(!opaque(x,y)||ignored(x,y)||!dirs.some(([dx,dy])=>!opaque(x+dx,y+dy)))continue;
 exposed++;const rgb=atlas.subarray(at(x,y),at(x,y)+3).toString('hex');
 if(!dark.has(rgb)){missing++;if(samples.length<12)samples.push({x,y,rgb})}
 }
 frames.push({pose:f+1,exposed,missing,samples});report.exposed+=exposed;report.missing+=missing;
}
report.facings[facing]={missing:frames.reduce((a,f)=>a+f.missing,0),frames};
}
report.status=report.exposed&&report.missing===0?'passed':'missing_leg_outline';
const reportPath=path.resolve(root,process.argv[3]||'output/review/R1-C8-OUTLINE/outline-current.json');
fs.mkdirSync(path.dirname(reportPath),{recursive:true});
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,exposed:report.exposed,missing:report.missing,by_facing:Object.fromEntries(Object.entries(report.facings).map(([k,v])=>[k,v.missing]))}));
if(report.status!=='passed')process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
