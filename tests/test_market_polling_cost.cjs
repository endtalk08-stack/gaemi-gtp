const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=100000,chart=false;const calls=[],intervals=[],events={},sockets=[],messages=[];const classes=new Set();
const list={addEventListener(){},querySelector(){return null;},querySelectorAll(){return[];},replaceChildren(){},textContent:''};
const sidebar={dataset:{},querySelector(s){return s==='#marketRankingList'?list:null;},querySelectorAll(){return[];}};
const document={visibilityState:'visible',body:{classList:{contains:x=>classes.has(x)}},getElementById:x=>x==='leftMarketSidebar'?sidebar:null,addEventListener:(n,f)=>events[n]=f};
class WebSocket {
 static CLOSING = 2;
 constructor(url){this.url=url;this.readyState=1;sockets.push(this);}
 close(){this.readyState=3;this.onclose?.();}
}
const window={WebSocket,innerWidth:1200,location:{hostname:'localhost',origin:'http://local'},addEventListener(){},dispatchEvent(event){messages.push(event);},setInterval:f=>intervals.push(f),setTimeout:()=>1,clearTimeout(){},GaemiGTPWidgetDock:{isActive:()=>false,isInlineChartActive:()=>chart}};
const context={AbortController,window,document,localStorage:{getItem:()=>null},Date:class extends Date{static now(){return now;}},console,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},fetch:async u=>{calls.push(u);return {ok:false};}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../frontend/shell/left-market-sidebar/market-sidebar.js','utf8'),context);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 events.DOMContentLoaded();await flush();assert.equal(calls.length,0,'closed sidebar must not query ranking');
 classes.add('left-market-open');window.GaemiGTPMarketSidebar.refreshLiveQuotes();await flush();assert.equal(calls.length,1);
 for(let i=0;i<10;i++){intervals[0]();await flush();}assert.equal(calls.length,1,'failed ranking must not retry every three seconds');
 now+=15001;intervals[0]();await flush();assert.equal(calls.length,2);
 classes.delete('left-market-open');now+=300001;intervals[0]();await flush();assert.equal(calls.length,2);
 chart=true;intervals[0]();await flush();
 assert.equal(sockets.length,2);
 assert.equal(sockets.at(-1).url,'wss://quotes.gaemigtp.com/ws/us-live-quotes');
 assert.equal(calls.filter(x=>x.includes('trading-value')).length,2);
 assert(!calls.some(url=>url.includes('/market/us-live-quotes')));
 sockets.at(-1).onmessage({data:JSON.stringify({type:'quotes',items:[
   {symbol:'MU',price:123,change_pct:1.2,received_at_ms:now,stale:false},
   {symbol:'NVDA',price:123,change_pct:1.2,received_at_ms:now-26000,stale:true},
 ]})});
 assert.equal(messages.at(-1).type,'gaemi:us-live-quotes');
 assert.deepEqual(Array.from(messages.at(-1).detail.items,q=>q.symbol),['MU']);
 document.visibilityState='hidden';let before=calls.length;events.visibilitychange();intervals[0]();await flush();
 assert.equal(calls.length,before,'background tab must stop all polls');
 assert.equal(sockets.at(-1).readyState,3,'background tab must close the quote socket');
 console.log('PASS: closed/sidebar/background gating, shared chart quotes, exponential ranking retry');
})().catch(e=>{console.error(e);process.exit(1)});

