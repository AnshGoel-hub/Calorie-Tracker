/* 3D anatomy viewer for the Workouts page.
   Needs the global THREE (three.js r128). Builds a mannequin plus ~36 separate muscles (heads split out)
   from primitives, so there are no model files to download. Exposes the global Anatomy3D. */
const Anatomy3D=(()=>{
"use strict";
// ---------------------------------------------------------------- data
// Shapes are for the RIGHT side of the body (x>0); the left side is mirrored automatically.
// E = ellipsoid: centre, radii, optional rotation.  S = spindle between points a and b: radii (x,z), offset.
// y is up, z points to the front of the body, the feet are at y=0 and the head top is about y=1.8.
const E=(c,r,rot)=>({k:"e",c,r,rot:rot||[0,0,0]});
const S=(a,b,r,off)=>({k:"s",a,b,r,off:off||[0,0,0]});
// g = muscle group used by the workout stats (ch sh bi tr fo ab la tp lb gl qd ha ca)
const MUSCLES=[
 // chest
 {id:"pec_clav",n:"Pectoralis major, clavicular head (upper chest)",g:"ch",f:"Lifts the arm forward and up. Builds the upper-chest shelf.",t:"Incline angles (15–30°) shift the work here.",ex:["ibp","dbp","ohp"],sh:E([.085,1.385,.07],[.085,.04,.04],[0,0,-.2])},
 {id:"pec_ster",n:"Pectoralis major, sternal head (mid chest)",g:"ch",f:"The big middle section. Pushes the arm forward and across the body.",t:"Flat pressing and flys work it hardest.",ex:["bp","dbp","chf","pu"],sh:E([.09,1.315,.085],[.095,.05,.04])},
 {id:"pec_cost",n:"Pectoralis major, costal fibers (lower chest)",g:"ch",f:"Pulls the arm down and in. Gives the chest its lower edge.",t:"Dips with a forward lean and decline presses bias it.",ex:["dip","bp","chf"],sh:E([.10,1.245,.08],[.08,.035,.035],[0,0,.2])},
 // shoulders
 {id:"del_ant",n:"Deltoid, anterior (front)",g:"sh",f:"Raises the arm in front of you and helps every pressing move.",t:"Already busy in chest pressing, so it rarely needs much direct work.",ex:["ohp","ibp","bp"],sh:E([.235,1.405,.04],[.04,.058,.036])},
 {id:"del_lat",n:"Deltoid, lateral (side)",g:"sh",f:"Raises the arm out to the side. Creates shoulder width.",t:"Lateral raises isolate it; keep the weight light and the reps controlled.",ex:["lr","ohp"],sh:E([.272,1.40,0],[.032,.06,.04])},
 {id:"del_post",n:"Deltoid, posterior (rear)",g:"sh",f:"Pulls the arm back and out. Balances all the pressing and helps posture.",t:"Rows and face pulls hit it too; rear-delt flys isolate it.",ex:["rdf","fcp","row","bor"],sh:E([.235,1.405,-.04],[.04,.058,.036])},
 {id:"cuff",n:"Infraspinatus and teres minor (rotator cuff)",g:"sh",f:"Rotates the arm outward and keeps the shoulder joint stable.",t:"Light, high-rep external rotation and face pulls keep shoulders healthy.",ex:["fcp","rdf"],sh:E([.14,1.36,-.09],[.05,.04,.02])},
 // arms
 {id:"bi_long",n:"Biceps, long head (outer)",g:"bi",f:"Crosses the shoulder as well as the elbow. Gives the biceps its peak.",t:"Stretched most when the elbow is behind the body (incline curls).",ex:["bc","hc"],sh:S([.245,1.35,0],[.285,1.17,0],[.019,.024],[.012,0,.034])},
 {id:"bi_short",n:"Biceps, short head (inner)",g:"bi",f:"Adds thickness to the inner side of the arm.",t:"Favored by preacher curls, elbows forward and a slightly wider grip.",ex:["bc","chn","pul"],sh:S([.245,1.35,0],[.285,1.17,0],[.019,.024],[-.010,0,.034])},
 {id:"brach",n:"Brachialis",g:"bi",f:"Sits under the biceps and flexes the elbow whatever your grip. Pushes the biceps up.",t:"Hammer and reverse-grip curls load it the most.",ex:["hc","bc"],sh:S([.26,1.27,0],[.288,1.14,0],[.02,.018],[.02,0,.022])},
 {id:"tr_long",n:"Triceps, long head",g:"tr",f:"The largest head and the only one crossing the shoulder.",t:"Overhead extensions stretch it most; it makes up most of the triceps' size.",ex:["oe","sk","dip"],sh:S([.245,1.36,0],[.29,1.17,0],[.022,.024],[-.008,0,-.034])},
 {id:"tr_lat",n:"Triceps, lateral head (outer)",g:"tr",f:"Forms the horseshoe on the outside of the arm. Works hard in heavy pressing.",t:"Pushdowns and close-grip pressing bring it in.",ex:["tpd","bp","dip"],sh:S([.255,1.35,0],[.288,1.18,0],[.02,.022],[.022,0,-.026])},
 {id:"tr_med",n:"Triceps, medial head",g:"tr",f:"Deep head that works in every elbow extension, light or heavy.",t:"Pushdowns and skull crushers keep tension on it.",ex:["tpd","sk"],sh:S([.27,1.26,0],[.292,1.14,0],[.02,.018],[0,0,-.034])},
 {id:"fo_flex",n:"Wrist flexors (inner forearm)",g:"fo",f:"Curls the wrist and fingers toward the palm. Drives your grip.",t:"Heavy pulls build them; wrist curls isolate them.",ex:["wc","dl"],sh:S([.295,1.12,0],[.325,.92,0],[.02,.022],[-.008,0,.022])},
 {id:"fo_ext",n:"Wrist extensors (outer forearm)",g:"fo",f:"Lifts the wrist back. Balances the flexors and protects the elbow.",t:"Reverse wrist curls with a light weight work them.",ex:["wc"],sh:S([.298,1.12,0],[.328,.92,0],[.02,.02],[.006,0,-.022])},
 {id:"brr",n:"Brachioradialis",g:"fo",f:"Forearm muscle that helps flex the elbow, especially with a neutral or overhand grip.",t:"Hammer curls load it directly.",ex:["hc"],sh:S([.30,1.14,0],[.326,.97,0],[.016,.018],[.024,0,.006])},
 // core
 {id:"ab_up",n:"Rectus abdominis, upper",g:"ab",f:"Curls the ribcage toward the pelvis.",t:"Crunch and cable crunch variations focus here.",ex:["crn","cru"],sh:E([.037,1.15,.074],[.032,.045,.024])},
 {id:"ab_low",n:"Rectus abdominis, lower",g:"ab",f:"Tilts the pelvis up toward the ribs. Resists arching of the lower back.",t:"Leg raises and planks work it.",ex:["lrz","pk"],sh:E([.037,1.04,.07],[.031,.05,.022])},
 {id:"obl",n:"Obliques",g:"ab",f:"Rotate and side-bend the trunk, and brace it against twisting.",t:"Planks and cable work add to it; heavy carries are good too.",ex:["pk","cru"],sh:E([.125,1.08,.03],[.04,.085,.045])},
 // back
 {id:"trap_up",n:"Trapezius, upper",g:"tp",f:"Shrugs the shoulders and helps tilt the head.",t:"Shrugs and heavy deadlift holds.",ex:["shr","dl"],sh:E([.085,1.50,-.03],[.095,.035,.045],[0,0,-.25])},
 {id:"trap_mid",n:"Trapezius, middle and rhomboids",g:"tp",f:"Squeezes the shoulder blades together. Key for posture.",t:"Rows with a pause at the squeeze.",ex:["row","fcp","bor"],sh:E([.06,1.38,-.095],[.08,.04,.022])},
 {id:"trap_low",n:"Trapezius, lower",g:"tp",f:"Pulls the shoulder blades down and helps the arm go overhead.",t:"Pull-ups and face pulls; Y-raises isolate it.",ex:["fcp","pul"],sh:E([.04,1.26,-.10],[.05,.06,.02])},
 {id:"lat",n:"Latissimus dorsi",g:"la",f:"Pulls the arm down and back. Builds back width.",t:"Vertical pulls (pull-ups, pulldowns) and rows.",ex:["pul","lpd","chn","row"],sh:E([.12,1.20,-.075],[.07,.11,.03])},
 {id:"teres",n:"Teres major",g:"la",f:"The lat's helper, tucked behind the armpit.",t:"Works with the lats in every row and pulldown.",ex:["lpd","row","dbr"],sh:E([.165,1.30,-.075],[.04,.028,.025])},
 {id:"erector",n:"Erector spinae (lower back)",g:"lb",f:"Keeps the spine upright and extends it.",t:"Back extensions and hinges (deadlifts, RDLs) load it.",ex:["dl","hy","rdl","sq"],sh:E([.04,1.08,-.07],[.03,.11,.028])},
 // hips
 {id:"glute_max",n:"Gluteus maximus",g:"gl",f:"The biggest hip extensor. Powers standing up, squatting and sprinting.",t:"Hip thrusts and deep squats train it hardest.",ex:["hth","sq","rdl","dl","lg"],sh:E([.075,.915,-.085],[.085,.075,.055])},
 {id:"glute_med",n:"Gluteus medius",g:"gl",f:"Lifts the leg out to the side and keeps the pelvis level when you walk.",t:"Lunges and single-leg work challenge it.",ex:["lg","hth"],sh:E([.135,1.0,-.035],[.04,.04,.06])},
 // thighs
 {id:"rf",n:"Rectus femoris",g:"qd",f:"The quad head that crosses the hip too. Extends the knee and flexes the hip.",t:"Leg extensions with the torso leaned back stretch it.",ex:["lex","sq","lp"],sh:S([.09,.90,0],[.10,.55,0],[.03,.03],[0,0,.052])},
 {id:"vl",n:"Vastus lateralis (outer quad)",g:"qd",f:"The largest quad head. Gives the thigh its sweep.",t:"Squats and leg presses with a medium stance.",ex:["sq","lp","lg"],sh:S([.095,.88,0],[.105,.54,0],[.032,.032],[.045,0,.03])},
 {id:"vm",n:"Vastus medialis (teardrop)",g:"qd",f:"The inner quad above the knee. Finishes the last degrees of knee extension.",t:"Deep knee bend and leg extensions.",ex:["lex","sq","wsit"],sh:S([.095,.68,0],[.10,.51,0],[.03,.03],[-.035,0,.04])},
 {id:"bf",n:"Biceps femoris (outer hamstring)",g:"ha",f:"Bends the knee and extends the hip, and rotates the leg outward.",t:"Leg curls and straight-leg hinges.",ex:["lcu","rdl","dl"],sh:S([.09,.88,0],[.10,.53,0],[.027,.027],[.032,0,-.05])},
 {id:"st",n:"Semitendinosus (inner hamstring)",g:"ha",f:"Bends the knee and extends the hip.",t:"Romanian deadlifts load the stretched position.",ex:["rdl","lcu"],sh:S([.09,.88,0],[.10,.53,0],[.026,.027],[-.012,0,-.055])},
 {id:"sm",n:"Semimembranosus (inner hamstring)",g:"ha",f:"Deep inner hamstring. Same job: hip extension and knee flexion.",t:"Leg curls and RDLs.",ex:["lcu","rdl"],sh:S([.09,.88,0],[.10,.53,0],[.027,.027],[-.035,0,-.04])},
 // lower leg
 {id:"gas_m",n:"Gastrocnemius, medial head",g:"ca",f:"The inner calf bulge. Points the foot and helps bend the knee.",t:"Straight-knee calf raises.",ex:["cr"],sh:S([.10,.49,0],[.10,.28,0],[.03,.032],[-.02,0,-.04])},
 {id:"gas_l",n:"Gastrocnemius, lateral head",g:"ca",f:"The outer calf bulge.",t:"Straight-knee calf raises.",ex:["cr"],sh:S([.10,.49,0],[.10,.28,0],[.03,.032],[.022,0,-.04])},
 {id:"sol",n:"Soleus",g:"ca",f:"Deep calf muscle that works when the knee is bent. Built for endurance.",t:"Seated or bent-knee calf raises.",ex:["cr"],sh:S([.10,.38,0],[.10,.16,0],[.026,.028],[.004,0,-.032])},
 {id:"tib",n:"Tibialis anterior (shin)",g:"ca",f:"Lifts the front of the foot and controls the landing of each step.",t:"Walking and incline treadmill work it.",ex:["wk","tm"],sh:S([.10,.46,0],[.10,.14,0],[.017,.022],[.012,0,.035])}
];
const BODY=[
 E([0,1.69,.005],[.085,.105,.095]),S([0,1.50,0],[0,1.62,0],[.045,.045]),
 E([0,1.29,-.005],[.185,.17,.105]),E([0,1.09,0],[.145,.15,.09]),E([0,.95,-.01],[.165,.10,.10]),
 E([.235,1.41,0],[.05,.05,.05]),S([.235,1.40,0],[.29,1.13,0],[.038,.038]),
 S([.29,1.13,0],[.33,.87,0],[.032,.030]),E([.34,.80,0],[.022,.05,.035]),
 S([.09,.95,0],[.10,.50,0],[.07,.07]),E([.10,.50,0],[.05,.05,.05]),S([.10,.50,0],[.10,.10,0],[.045,.045]),
 E([.10,.05,.05],[.04,.04,.10])
];
const MAP={};MUSCLES.forEach(m=>MAP[m.id]=m);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

// ---------------------------------------------------------------- geometry
function place(mesh,sh,sx){
 const V=THREE.Vector3;
 if(sh.k==="e"){
  mesh.position.set(sh.c[0]*sx,sh.c[1],sh.c[2]);mesh.scale.set(sh.r[0],sh.r[1],sh.r[2]);
  mesh.rotation.set(sh.rot[0],sh.rot[1]*sx,sh.rot[2]*sx);
 }else{
  const a=new V(sh.a[0]*sx,sh.a[1],sh.a[2]),b=new V(sh.b[0]*sx,sh.b[1],sh.b[2]),d=b.clone().sub(a),len=d.length();
  mesh.position.copy(a).add(b).multiplyScalar(.5).add(new V(sh.off[0]*sx,sh.off[1],sh.off[2]));
  mesh.scale.set(sh.r[0],len/2*1.08,sh.r[1]);
  mesh.quaternion.setFromUnitVectors(new V(0,1,0),d.normalize());
 }
}
function build(){
 const geo=new THREE.SphereGeometry(1,28,18),body=[],muscles=[];
 const bodyMat=new THREE.MeshPhongMaterial({color:0x999999,shininess:8,specular:0x111111});
 BODY.forEach(sh=>[1,-1].forEach(sx=>{
  if(sx<0&&Math.abs(sh.k==="e"?sh.c[0]:sh.a[0])<.001&&Math.abs(sh.k==="e"?0:sh.b[0])<.001)return; // centre line parts once
  const m=new THREE.Mesh(geo,bodyMat);place(m,sh,sx);body.push(m)}));
 MUSCLES.forEach((def,i)=>{
  const mat=new THREE.MeshPhongMaterial({color:0x888888,shininess:25,specular:0x222222}),
   omat=new THREE.MeshBasicMaterial({color:0xffffff,side:THREE.BackSide}),meshes=[];
  [1,-1].forEach(sx=>{
   const m=new THREE.Mesh(geo,mat);place(m,def.sh,sx);m.userData.id=def.id;
   const o=new THREE.Mesh(geo,omat);o.scale.setScalar(1.09);o.visible=false;m.add(o);m.userData.outline=o;
   meshes.push(m)});
  muscles.push({def,i,mat,omat,meshes});
 });
 return{geo,body,bodyMat,muscles};
}

// ---------------------------------------------------------------- viewer
function create(el,opts){
 opts=opts||{};
 const B=build(),scene=new THREE.Scene(),T=new THREE.Vector3(0,.95,0);
 const cam=new THREE.PerspectiveCamera(32,1,.1,50);
 let renderer;
 try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true})}catch(e){throw new Error("WebGL unavailable")}
 if(!renderer.getContext())throw new Error("WebGL unavailable");
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setClearColor(0x000000,0);
 const cv=renderer.domElement;cv.style.cssText="display:block;width:100%;height:100%;touch-action:pan-y;cursor:grab";
 cv.setAttribute("role","img");cv.setAttribute("aria-label","Interactive 3D muscle model. Drag to rotate, click a muscle for details.");
 el.appendChild(cv);
 const tip=document.createElement("div");tip.className="a3-tip";tip.hidden=true;el.appendChild(tip);
 B.body.forEach(m=>scene.add(m));B.muscles.forEach(o=>o.meshes.forEach(m=>scene.add(m)));
 scene.add(new THREE.AmbientLight(0xffffff,.62));
 const key=new THREE.DirectionalLight(0xffffff,.62);key.position.set(1.2,1.6,2.4);cam.add(key);
 const fill=new THREE.DirectionalLight(0xffffff,.22);fill.position.set(-2,-.4,1);cam.add(fill);scene.add(cam);

 const pick=[].concat(B.body,...B.muscles.map(o=>o.meshes));
 const ray=new THREE.Raycaster(),ndc=new THREE.Vector2();
 let st={th:0,ph:.1,d:3.6},goal=null,raf=0,selId=null,hovId=null,data={vals:{},mode:"week",max:1};
 const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim()||"#888888";
 const col=n=>new THREE.Color(css(n));

 function camPlace(){
  const c=Math.cos(st.ph);
  cam.position.set(T.x+st.d*Math.sin(st.th)*c,T.y+st.d*Math.sin(st.ph),T.z+st.d*Math.cos(st.th)*c);cam.lookAt(T)}
 function size(){
  const w=el.clientWidth,h=el.clientHeight;if(!w||!h)return;
  renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();dirty()}
 function frame(){
  raf=0;
  if(goal){
   const k=.18;st.th+=(goal.th-st.th)*k;st.ph+=(goal.ph-st.ph)*k;st.d+=(goal.d-st.d)*k;
   if(Math.abs(goal.th-st.th)<.003&&Math.abs(goal.ph-st.ph)<.003&&Math.abs(goal.d-st.d)<.01){st.th=goal.th;st.ph=goal.ph;st.d=goal.d;goal=null}
  }
  camPlace();renderer.render(scene,cam);
  if(goal)raf=requestAnimationFrame(frame)}
 function dirty(){if(!raf)raf=requestAnimationFrame(frame)}

 // colours --------------------------------------------------------
 function paintMuscle(o){
  const sel=o.def.id===selId,hov=o.def.id===hovId,sib=selId&&MAP[selId].g===o.def.g&&!sel;
  o.mat.emissive.copy(o.mat.color).multiplyScalar(sel?.5:hov?.3:sib?.16:0);
  o.meshes.forEach(m=>{const ol=m.userData.outline;ol.visible=sel||hov;});
  o.omat.color.copy(sel?col("--ac"):col("--tx"));
 }
 function recolor(){
  const bd=col("--bd"),mu=col("--mu"),none=bd.clone().lerp(mu,.5);
  B.bodyMat.color.copy(bd.clone().lerp(mu,.22));
  const wa=col("--wa"),wt=col("--wt"),bad=col("--bad"),ac=col("--ac");
  B.muscles.forEach(o=>{
   const v=data.vals[o.def.g]||0;let c;
   if(v<=0)c=none.clone();
   else if(data.mode==="session")c=none.clone().lerp(ac,.35+.65*clamp(v/(data.max||1),0,1));
   else c=v<10?none.clone().lerp(wa,.45+.055*v):v<=20?wt.clone():bad.clone();
   c.offsetHSL(0,0,((o.i*37)%5-2)*.022); // tiny shade change so neighbouring heads stay distinguishable
   o.mat.color.copy(c);paintMuscle(o)});
  dirty()}

 // picking --------------------------------------------------------
 function hit(e){
  const r=cv.getBoundingClientRect();
  ndc.set((e.clientX-r.left)/r.width*2-1,-((e.clientY-r.top)/r.height)*2+1);
  ray.setFromCamera(ndc,cam);
  const h=ray.intersectObjects(pick,false)[0];
  return h?h.object.userData.id||null:null}
 function setHover(id,e){
  if(id===hovId){if(id&&e)moveTip(e);return}
  hovId=id;B.muscles.forEach(paintMuscle);cv.style.cursor=id?"pointer":"grab";
  if(id&&e){tip.textContent=MAP[id].n;tip.hidden=false;moveTip(e)}else tip.hidden=true;
  dirty()}
 function moveTip(e){const r=el.getBoundingClientRect();tip.style.left=clamp(e.clientX-r.left+14,4,r.width-170)+"px";tip.style.top=clamp(e.clientY-r.top+14,4,r.height-34)+"px"}
 function select(id,o){
  id=id&&MAP[id]?id:null;selId=id;B.muscles.forEach(paintMuscle);dirty();
  if(id&&o&&o.focus){
   const m=MAP[id],s=m.sh,z=s.k==="e"?s.c[2]:(s.a[2]+s.b[2])/2+s.off[2],x=s.k==="e"?s.c[0]:(s.a[0]+s.b[0])/2+s.off[0];
   view(z<-.02?"back":"front");
  }
  if(opts.onSelect&&!(o&&o.silent))opts.onSelect(id)}

 // input ------------------------------------------------------------
 const ptrs=new Map();let down=null,hovBusy=false;
 cv.addEventListener("pointerdown",e=>{
  try{cv.setPointerCapture(e.pointerId)}catch(x){}
  ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});down={x:e.clientX,y:e.clientY,t:performance.now(),mv:0};goal=null;cv.style.cursor="grabbing"});
 cv.addEventListener("pointermove",e=>{
  const p=ptrs.get(e.pointerId);
  if(p){
   const dx=e.clientX-p.x,dy=e.clientY-p.y;p.x=e.clientX;p.y=e.clientY;
   if(down)down.mv+=Math.abs(dx)+Math.abs(dy);
   st.th-=dx*.008;st.ph=clamp(st.ph+dy*.006,-.5,1.1);setHover(null);dirty();
  }else if(e.pointerType==="mouse"&&!hovBusy){
   hovBusy=true;requestAnimationFrame(()=>{hovBusy=false;setHover(hit(e),e)})}});
 const end=e=>{
  ptrs.delete(e.pointerId);cv.style.cursor=hovId?"pointer":"grab";
  if(e.type==="pointerup"&&down&&down.mv<6&&performance.now()-down.t<700){const id=hit(e);select(id===selId?null:id)}
  down=null};
 cv.addEventListener("pointerup",end);cv.addEventListener("pointercancel",end);
 cv.addEventListener("pointerleave",()=>setHover(null));
 cv.addEventListener("wheel",e=>{e.preventDefault();goal=null;st.d=clamp(st.d*(e.deltaY>0?1.08:.92),1.4,5.5);dirty()},{passive:false});
 cv.addEventListener("keydown",e=>{
  const k={ArrowLeft:[-.2,0],ArrowRight:[.2,0],ArrowUp:[0,-.15],ArrowDown:[0,.15]}[e.key];
  if(k){e.preventDefault();st.th+=k[0];st.ph=clamp(st.ph+k[1],-.5,1.1);dirty()}});
 cv.tabIndex=0;

 function view(name){
  const t={front:0,back:Math.PI,left:-Math.PI/2,right:Math.PI/2}[name];if(t===undefined)return;
  const th=t+Math.PI*2*Math.round((st.th-t)/(Math.PI*2));
  goal={th,ph:.1,d:st.d};dirty()}
 function zoom(f){goal={th:st.th,ph:st.ph,d:clamp(st.d*f,1.4,5.5)};dirty()}
 function reset(){goal={th:Math.round(st.th/(Math.PI*2))*Math.PI*2,ph:.1,d:3.6};dirty()}

 const ro=typeof ResizeObserver!=="undefined"?new ResizeObserver(size):null;
 if(ro)ro.observe(el);else addEventListener("resize",size);
 size();recolor();

 return{
  setData(vals,mode,max){data={vals:vals||{},mode:mode||"week",max:max||1};recolor()},
  refresh:recolor,select,view,zoom,reset,resize:size,
  get selected(){return selId},
  dispose(){if(ro)ro.disconnect();renderer.dispose();cv.remove();tip.remove()}
 };
}

return{create,MUSCLES,byId:id=>MAP[id],_build:build};
})();
