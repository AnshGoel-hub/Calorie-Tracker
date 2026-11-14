/* Calorie target suggestion (Mifflin-St Jeor). A rough estimate, not medical advice. */
const Goals=(()=>{
 const ACT=[["sedentary","Mostly sitting (little exercise)",1.2],["light","Light (1–3 workouts/week)",1.375],["moderate","Moderate (3–5 workouts/week)",1.55],["very","Very active (6–7 workouts/week)",1.725]];
 const GOAL=[["lose","Lose weight slowly"],["maintain","Maintain weight"],["gain","Gain weight slowly"]];
 const fill=(el,list,val)=>{el.innerHTML=list.map(o=>'<option value="'+o[0]+'">'+o[1]+'</option>').join("");if(val)el.value=val};
 const n=x=>Math.round(x).toLocaleString("en-IN");
 function calc(p,kg){
  p=p||{};const a=+p.age,h=+p.height,w=+kg;
  if(!(a>0&&h>0&&w>0))return{err:"Enter your age, height and weight to get a suggestion."};
  if(a<18)return{err:"Calorie suggestions are for adults (18+). Please set your own target, ideally with a parent, guardian or doctor."};
  if(a>100||h<120||h>230||w<30||w>250)return{err:"Those numbers look off. Check age, height (cm) and weight (kg)."};
  if(p.sex!=="male"&&p.sex!=="female")return{err:"Choose male or female (the formula needs one)."};
  const bmr=10*w+6.25*h-5*a+(p.sex==="male"?5:-161),f=(ACT.find(x=>x[0]===p.activity)||ACT[0])[2],tdee=bmr*f,bmi=w/((h/100)**2);
  const d=p.goal==="lose"?-Math.min(400,Math.round(.2*tdee)):p.goal==="gain"?300:0;
  if(d<0&&bmi<18.5)return{err:"Your BMI is under 18.5, so a calorie deficit isn't suggested. Choose maintain or gain, and consider talking to a doctor."};
  const floor=p.sex==="male"?1500:1200;let t=Math.round((tdee+d)/50)*50,capped=false;
  if(t<floor){t=floor;capped=true}
  const lab={lose:"slow weight loss",gain:"slow weight gain"}[p.goal]||"maintaining weight";
  return{target:t,note:"Maintenance ≈ "+n(Math.round(tdee/50)*50)+" kcal. Suggested for "+lab+": "+n(t)+" kcal/day"+(capped?" (raised to a safe minimum)":"")+". Rough estimate, not medical advice."};
 }
 return{ACT,GOAL,fill,calc};
})();
