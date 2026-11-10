/**
 * Existing gaemigtp-news Pages delivery, extended with US TOP20 only.
 * R2 news behavior is kept equivalent to functions/news/latest.json.js.
 * Uses the existing NEWS_R2 binding; no Neon, Render or new credentials.
 */
const TOP20_URL = "https://quotes.gaemigtp.com/market/trading-value?market=us";
const NEWS_KEY = "news/latest.json";
const json = (body, status, cache="no-store") => new Response(JSON.stringify(body), {
  status, headers: {"Content-Type":"application/json; charset=utf-8",
                   "Cache-Control":cache,"X-Content-Type-Options":"nosniff"}
});

async function news(request, env) {
  if (!env.NEWS_R2 || typeof env.NEWS_R2.get !== "function") {
    return json({ok:false,error:"news_storage_unavailable"},503);
  }
  let object;
  try { object=await env.NEWS_R2.get(NEWS_KEY); }
  catch (error) {
    console.error("news_r2_read_failed",error?.name||"Error");
    return json({ok:false,error:"news_storage_unavailable"},503);
  }
  if (!object) return json({ok:false,error:"news_not_found"},404);
  const etag=object.httpEtag;
  if(etag&&request.headers.get("If-None-Match")===etag)
    return new Response(null,{status:304,headers:{ETag:etag,"Cache-Control":"public, max-age=60"}});
  const headers=new Headers({"Content-Type":"application/json; charset=utf-8",
    "Cache-Control":"public, max-age=60, stale-while-revalidate=60",
    "X-Content-Type-Options":"nosniff"});
  if(etag)headers.set("ETag",etag);
  return new Response(object.body,{status:200,headers});
}

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
    if(request.method==="GET"&&url.pathname==="/news/latest.json")return news(request,env);
    if(request.method==="GET"&&url.pathname==="/market/trading-value"&&url.searchParams.get("market")==="us")return top20();
    return env.ASSETS.fetch(request);
  }
};
