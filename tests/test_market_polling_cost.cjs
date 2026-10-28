const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=100000,chart=false;const calls=[],intervals=[],events={};const classes=new Set();
const list={addEventListener(){},querySelector(){return null;},querySelectorAll(){return[];},replaceChildren(){},textContent:''};
const sidebar={dataset:{},querySelector(s){return s==='#marketRankingList'?list:null;},querySelectorAll(){return[];}};
const document={visibilityState:'visible',body:{classList:{contains:x=>classes.has(x)}},getElementById:x=>x==='leftMarketSidebar'?sidebar:null,addEventListener:(n,f)=>events[n]=f};
const window={innerWidth:1200,location:{hostname:'localhost',origin:'http://local'},addEventListener(){},dispatchEvent(){},setInterval:f=>intervals.push(f),GaemiGTPWidgetDock:{isActive:()=>false,isInlineChartActive:()=>chart}};
const context={window,document,localStorage:{getItem:()=>null},Date:class extends Date{static now(){return now;}},console,CustomEvent:class{},fetch:async u=>{calls.push(u);return {ok:false};}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../frontend/shell/left-market-sidebar/market-sidebar.js','utf8'),context);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 events.DOMContentLoaded();await flush();assert.equal(calls.length,0,'closed sidebar must not query ranking');
 classes.add('left-market-open');window.GaemiGTPMarketSidebar.refreshLiveQuotes();await flush();assert.equal(calls.length,1);
 for(let i=0;i<10;i++){intervals[0]();await flush();}assert.equal(calls.length,1,'failed ranking must not retry every three seconds');
 now+=15001;intervals[0]();await flush();assert.equal(calls.length,2);
 classes.delete('left-market-open');now+=300001;intervals[0]();await flush();assert.equal(calls.length,2);
 chart=true;intervals[0]();await flush();assert(calls.at(-1).endsWith('/market/us-live-quotes'));assert.equal(calls.filter(x=>x.includes('trading-value')).length,2);
 document.visibilityState='hidden';let before=calls.length;intervals[0]();await flush();assert.equal(calls.length,before,'background tab must stop all polls');
 console.log('PASS: closed/sidebar/background gating, shared chart quotes, exponential ranking retry');
})().catch(e=>{console.error(e);process.exit(1)});
