/**
 * US TOP20 Pages delivery only.
 * News is delivered by the gaemiGTP news widget, not this retired standalone page.
 */
const TOP20_URL = "https://quotes.gaemigtp.com/market/trading-value?market=us";
const json = (body, status, cache="no-store") => new Response(JSON.stringify(body), {
  status, headers: {"Content-Type":"application/json; charset=utf-8",
                   "Cache-Control":cache,"X-Content-Type-Options":"nosniff"}
});

async function top20() {
  let response;
  try {
    response=await fetch(TOP20_URL,{
      headers:{"Accept":"application/json","User-Agent":"Mozilla/5.0"},
      redirect:"error",
      signal:AbortSignal.timeout(8000)
    });
  } catch (error) {
    console.error("top20_upstream_connection_error",error?.name||"Error");
    return json({ok:false,error:"top20_origin_unreachable",items:[]},502);
  }
  if (!response.ok) {
    console.error("top20_upstream_http",response.status);
    return json({ok:false,error:"top20_origin_unavailable",items:[]},502);
  }
  let data;
  try {data=await response.json();}
  catch {return json({ok:false,error:"top20_invalid_json",items:[]},502);}
  if(data?.ok!==true || data?.source!=="kiwoom" || !Array.isArray(data.items)||
     data.items.length!==20 || data.items.some((row,i)=>!row||row.rank!==i+1||!row.symbol)){
    return json({ok:false,error:"top20_invalid_payload",items:[]},502);
  }
  return json({ok:true,market:"us",source:"kiwoom",currency:"USD",
    captured_at:data.captured_at,items:data.items},200,"public, max-age=15");
}

export default {
  async fetch(request,env,ctx) {
    const url=new URL(request.url);
    if(request.method==="GET"&&url.pathname==="/market/trading-value"&&url.searchParams.get("market")==="us")return top20();
    return env.ASSETS.fetch(request);
  }
};
