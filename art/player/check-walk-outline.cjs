const fs=require('fs'),path=require('path'),sharp=require('sharp');
// Validate the actual baked PNG contour; optional arguments: source-directory report-path.
const root=path.resolve(__dirname,'../..'),art=__dirname,cfg=require(path.join(art,'consistent-rig.json'));
for(const file of ['consistent-front-back.json','consistent-side.json','consistent-diagonal.json'])Object.assign(cfg.facings,require(path.join(art,file)));
const dark=new Set(['15141b','242633','392b29']),dirs=[[1,0],[-1,0],[0,1],[0,-1]];
const navy=new Set(['15141b','242633','323648','42495f','555d77','69728e']);
const sourceDir=path.resolve(root,process.argv[2]||'game/assets/player');
// Align the excluded equipment mask with the baked grip/shaft pose.
function posedBat(source,rig){
 if(!rig.batRotation)return source;
 const {pivot,targetPivot=pivot,degrees,axisEnd,lengthScale=1}=rig.batRotation,angle=degrees*Math.PI/180;
 const axis=axisEnd?[axisEnd[0]-pivot[0],axisEnd[1]-pivot[1]]:[0,1],length=Math.hypot(...axis);
 const su=axis.map(v=>v/length),c=Math.cos(angle),s=Math.sin(angle),du=[c*su[0]-s*su[1],s*su[0]+c*su[1]];
 const scale=axisEnd?lengthScale:1,result=Buffer.alloc(source.length);
 for(let y=0;y<80;y++)for(let x=0;x<80;x++){
  const px=x-targetPivot[0],py=y-targetPivot[1],along=(px*du[0]+py*du[1])/scale,across=-px*du[1]+py*du[0];
  const sx=Math.round(pivot[0]+su[0]*along-su[1]*across),sy=Math.round(pivot[1]+su[1]*along+su[0]*across);
  if(sx<0||sx>=80||sy<0||sy>=80)continue;
  const from=(sy*80+sx)*4;if(source[from+3])source.copy(result,(y*80+x)*4,from,from+4);
 }
 return result;
}
(async()=>{
const report={scope:'Lower-leg boundary excludes fixed body/bat; side hip band also inspects body-owned garment edges and a visible inner-thigh seam',dark_colors:[...dark],hip_outline_color:'15141b',facings:{},exposed:0,missing:0,hip_exposed:0,hip_missing:0,seam_missing:0};
for(const [facing,rig] of Object.entries(cfg.facings)){
const slug=facing.replaceAll('_','-'),{data:atlas}=await sharp(path.join(sourceDir,'r1-consistent-'+slug+'-20261105.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
const body=await sharp(path.join(art,'consistent-parts',slug,'body.png')).ensureAlpha().raw().toBuffer();
const batSlug=(rig.batSourceFacing||facing).replaceAll('_','-');
const bat=posedBat(await sharp(path.join(art,'consistent-parts',batSlug,'bat.png')).ensureAlpha().raw().toBuffer(),rig);
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
 let hipExposed=0,hipMissing=0,seamMissing=0;const hipSamples=[];
 if(facing==='left'||facing==='right'){
  const hips=[rig.legs.right.hip,rig.legs.left.hip];
  const y0=Math.floor(Math.min(...hips.map(h=>h[1])))-2+drop,y1=Math.ceil(Math.max(...hips.map(h=>h[1])))+5+drop;
  const x0=Math.floor(Math.min(...hips.map(h=>h[0])))-8,x1=Math.ceil(Math.max(...hips.map(h=>h[0])))+8;
  for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
   const rgb=atlas.subarray(at(x,y),at(x,y)+3).toString('hex');
   if(!opaque(x,y)||!navy.has(rgb)||!dirs.some(([dx,dy])=>!opaque(x+dx,y+dy)))continue;
   hipExposed++;if(rgb!=='15141b'){hipMissing++;hipSamples.push({x,y,rgb});}
  }
  // Actual reported defect: visible near/far boundary, invisible to alpha-only perimeter checks.
  if(facing==='left'&&f===0){
   const x=40,y=50,rgb=atlas.subarray(at(x,y),at(x,y)+3).toString('hex');
   if(!opaque(x,y)||rgb!=='15141b'){seamMissing++;hipSamples.push({x,y,rgb,kind:'inner_thigh_seam'});}
  }
 }
 frames.push({pose:f+1,exposed,missing,samples,hip_exposed:hipExposed,hip_missing:hipMissing,seam_missing:seamMissing,hip_samples:hipSamples});
 report.exposed+=exposed;report.missing+=missing;report.hip_exposed+=hipExposed;report.hip_missing+=hipMissing;report.seam_missing+=seamMissing;
}
report.facings[facing]={missing:frames.reduce((a,f)=>a+f.missing,0),hip_missing:frames.reduce((a,f)=>a+f.hip_missing,0),seam_missing:frames.reduce((a,f)=>a+f.seam_missing,0),frames};
}
report.status=report.exposed&&report.missing===0&&report.hip_missing===0&&report.seam_missing===0?'passed':'missing_leg_outline';
const reportPath=path.resolve(root,process.argv[3]||'output/review/R1-C8-OUTLINE/outline-current.json');
fs.mkdirSync(path.dirname(reportPath),{recursive:true});
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,exposed:report.exposed,missing:report.missing,hip_missing:report.hip_missing,seam_missing:report.seam_missing,by_facing:Object.fromEntries(Object.entries(report.facings).map(([k,v])=>[k,{lower:v.missing,hip:v.hip_missing,seam:v.seam_missing}]))}));
if(report.status!=='passed')process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
