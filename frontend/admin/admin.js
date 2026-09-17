const KEY="gaemiGTP_admin_v1";
const defaults={
 data:[
  {id:1,name:"1분 거래대금",type:"minute_value",source:"증권사 API",enabled:true},
  {id:2,name:"5분 거래대금",type:"minute_value",source:"증권사 API",enabled:true},
  {id:3,name:"거래량",type:"volume",source:"증권사 API",enabled:true},
  {id:4,name:"실시간 순위",type:"rank",source:"키움 실시간",enabled:true}
 ],
 conditions:[
  {id:1,name:"거래대금 5배",expr:"평소 대비 거래대금 ≥ 5배",enabled:true},
  {id:2,name:"순위 급상승",expr:"실시간 순위 상승 ≥ 10단계",enabled:true}
 ],
 results:[
  {id:1,name:"+5분 가격 변화",expr:"이벤트 후 5분 수익률",enabled:true},
  {id:2,name:"+10분 가격 변화",expr:"이벤트 후 10분 수익률",enabled:true},
  {id:3,name:"최대 상승폭",expr:"이벤트 후 최대 상승률",enabled:true}
 ],
 messages:[
  {id:1,event:"거래대금 급증",text:"거래가 붙었어.",priority:1,enabled:true},
  {id:2,event:"순위 상승",text:"순위 올라왔어.",priority:2,enabled:true},
  {id:3,event:"전고점 돌파",text:"고점 넘었어.",priority:3,enabled:true},
  {id:4,event:"뉴스 확인",text:"뉴스 확인됐어.",priority:4,enabled:true}
 ],
 events:[
  {id:1,name:"거래대금 급증",condition:"거래대금 5배",enabled:true},
  {id:2,name:"순위 상승",condition:"순위 급상승",enabled:true},
  {id:3,name:"전고점 돌파",condition:"전고점 돌파",enabled:true},
  {id:4,name:"뉴스 확인",condition:"뉴스 존재",enabled:true}
 ]
};
let db=load();
function load(){try{return JSON.parse(localStorage.getItem(KEY))||structuredClone(defaults)}catch(e){return structuredClone(defaults)}}
function save(){localStorage.setItem(KEY,JSON.stringify(db))}
const labels={dashboard:"대시보드",data:"📡 데이터 수집",validation:"🧪 데이터 검증",conditions:"⚙ 조건 관리",results:"📊 검증 결과 / 조건 실현",messages:"💬 멘트 관리",events:"🧩 이벤트 관리",story:"🕐 Market Story",preview:"👀 미리보기",publish:"🚀 서비스 적용"};
const titles={data:"데이터 수집",conditions:"조건 관리",results:"검증 결과 / 조건 실현",messages:"멘트 관리",events:"이벤트 관리"};
function esc(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}
function table(type,items,cols){
 let rows=items.map(x=>`<tr>${cols.map(c=>`<td>${c==="enabled"?`<span class="switch ${x.enabled?"on":""}">${x.enabled?"ON":"OFF"}</span>`:esc(x[c])}</td>`).join("")}<td class="actions"><button class="ghost" onclick="toggle('${type}',${x.id})">ON/OFF</button><button class="ghost" onclick="editItem('${type}',${x.id})">수정</button><button class="danger" onclick="delItem('${type}',${x.id})">삭제</button></td></tr>`).join("");
 return `<table class="table"><thead><tr>${cols.map(c=>`<th>${c}</th>`).join("")}<th>관리</th></tr></thead><tbody>${rows||`<tr><td colspan="${cols.length+1}" class="empty">등록된 항목이 없습니다.</td></tr>`}</tbody></table>`;
}
function render(section="dashboard"){
 document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.section===section));
 document.getElementById("pageTitle").textContent=labels[section];
 const c=document.getElementById("content");
 if(section==="dashboard")return c.innerHTML=`<div class="grid">
  <div class="card"><h3>데이터 모듈</h3><div class="metric">${db.data.length}</div><div class="muted">등록된 데이터</div></div>
  <div class="card"><h3>조건</h3><div class="metric">${db.conditions.length}</div><div class="muted">검증 조건</div></div>
  <div class="card"><h3>멘트</h3><div class="metric">${db.messages.length}</div><div class="muted">등록된 멘트</div></div>
  <div class="card"><h3>이벤트</h3><div class="metric">${db.events.length}</div><div class="muted">등록된 이벤트</div></div>
  <div class="card full"><h3>현재 구조</h3><p class="muted">데이터 → 조건 → 검증 결과 → 이벤트 → 멘트 → Market Story → 서비스 적용</p></div>
 </div>`;
 if(section==="validation")return validation();
 if(section==="story")return story();
 if(section==="preview")return preview();
 if(section==="publish")return publish();
 const map={data:["데이터",["name","type","source","enabled"]],conditions:["조건",["name","expr","enabled"]],results:["검증 결과",["name","expr","enabled"]],messages:["멘트",["event","text","priority","enabled"]],events:["이벤트",["name","condition","enabled"]]};
 const [title,cols]=map[section];
 c.innerHTML=`<div class="toolbar"><h2>${title}</h2><button class="primary" onclick="addItem('${section}')">+ 추가</button></div>${table(section,db[section],cols)}`;
}
function validation(){
 document.getElementById("content").innerHTML=`<div class="grid">
 <div class="form full"><h2>데이터 검증</h2>
 <label>대상 데이터</label><select id="vdata"><option>1분 거래대금</option><option>5분 거래대금</option></select>
 <label>비교 대상</label><select id="vcomp"><option>1분 vs 5분 거래대금</option><option>거래량</option><option>실시간 순위</option></select>
 <label>조건</label><input id="vcond" value="평소 대비 5배 이상">
 <label>검증 기간</label><input type="date" id="vfrom"><input type="date" id="vto">
 <br><br><button class="primary" onclick="runValidation()">검증 실행</button>
 <div id="vout" class="empty">아직 실행하지 않았습니다.</div></div></div>`;
}
function runValidation(){
 document.getElementById("vout").innerHTML=`<div class="card"><h3>V1 검증 실행 준비 완료</h3><p class="muted">현재 화면은 조건을 정의하는 관리자 UI입니다. 실제 결과 계산은 PostgreSQL + 과거 분봉 데이터 연결 후 실행됩니다.</p></div>`;
}
function story(){
 const eventTimes={"거래대금 급증":"09:03","순위 상승":"09:05","전고점 돌파":"09:07","뉴스 확인":"09:09"};
 const messages=db.messages
   .filter(m=>m.enabled && m.event && m.text)
   .sort((a,b)=>(a.priority??999)-(b.priority??999));
 const uniqueEvents=new Set();
 const rows=messages.filter(m=>{
   if(uniqueEvents.has(m.event)) return false;
   uniqueEvents.add(m.event);
   return true;
 }).map(m=>[eventTimes[m.event]||"--:--",m.text]);
 const body=rows.length?rows.map(x=>'<div class="story-line"><div class="time">'+esc(x[0])+'</div><div>'+esc(x[1])+'</div></div>').join(""):"<div class=\"empty\">활성화된 멘트가 없습니다.</div>";
 document.getElementById("content").innerHTML=`<div class="story"><h2>Market Story</h2>${body}</div>`;
}
function preview(){document.getElementById("content").innerHTML=`<div class="form"><h2>실제 종목 미리보기</h2><label>종목</label><input id="stock" value="삼성전자"><br><br><button class="primary" onclick="alert('V1 미리보기: '+document.getElementById('stock').value)">미리보기</button></div>`}
function publish(){document.getElementById("content").innerHTML=`<div class="card"><h2>서비스 적용</h2><p>검증 완료된 모듈만 사용자 사이트에 연결하는 단계입니다.</p><span class="badge">현재: 관리자 V1 / 실제 서비스 연결 전</span></div>`}
function addItem(type){
 const names={data:["데이터 이름","1분 거래대금"],conditions:["조건 이름","평소 대비 거래대금 ≥ 5배"],results:["결과 이름","이벤트 후 +5분 수익률"],messages:["이벤트","거래대금 급증"],events:["이벤트 이름","거래대금 급증"]};
 const [label,val]=names[type]; const value=prompt(label,val); if(!value)return;
 const item={id:Date.now(),enabled:true};
 if(type==="data")Object.assign(item,{name:value,type:"custom",source:"직접 등록"});
 if(type==="conditions")Object.assign(item,{name:value,expr:prompt("조건식","평소 대비 5배 이상")||""});
 if(type==="results")Object.assign(item,{name:value,expr:prompt("검증 결과 계산식","이벤트 후 가격 변화")||""});
 if(type==="messages")Object.assign(item,{event:value,text:prompt("멘트","거래가 붙었어.")||"",priority:99});
 if(type==="events")Object.assign(item,{name:value,condition:prompt("연결 조건","")||""});
 db[type].push(item);save();render(type);
}
function editItem(type,id){
 const x=db[type].find(v=>v.id===id); if(!x)return;
 if(x.name!==undefined)x.name=prompt("이름",x.name)||x.name;
 if(type==="messages")x.text=prompt("멘트",x.text)||x.text;
 if(type==="conditions"||type==="results")x.expr=prompt("조건/계산식",x.expr)||x.expr;
 save();render(type);
}
function delItem(type,id){if(!confirm("삭제할까요?"))return;db[type]=db[type].filter(x=>x.id!==id);save();render(type)}
function toggle(type,id){const x=db[type].find(v=>v.id===id);if(x){x.enabled=!x.enabled;save();render(type)}}
document.getElementById("nav").addEventListener("click",e=>{const b=e.target.closest(".nav-item");if(b)render(b.dataset.section)});
document.getElementById("resetBtn").onclick=()=>{if(confirm("데모 데이터를 초기화할까요?")){db=structuredClone(defaults);save();render()}};
render();
