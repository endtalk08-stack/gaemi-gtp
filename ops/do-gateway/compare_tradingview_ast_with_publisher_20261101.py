"""Compare one TradingView AST article against its publisher page and Yahoo syndication.
Read-only: one API detail request, HTTP GET publisher URLs; no worker/DB/AI/cache writes.
"""
import json, os, re, urllib.parse, urllib.request, subprocess, html
from html.parser import HTMLParser

assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True,timeout=10).stdout.strip()=="inactive"
key=os.environ["TRADINGVIEW_API_KEY"].strip()
nid="stocktwits:8726df0b3094b:0"
api_url="https://api.tradingviewapi.com/api/news/"+urllib.parse.quote(nid,safe="")+"?lang=en"
def get(url, headers=None, limit=5_000_000):
    req=urllib.request.Request(url,headers=headers or {"User-Agent":"Mozilla/5.0","Accept":"text/html,application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.status,r.geturl(),r.headers.get("Content-Type",""),r.read(limit)
status,_,_,raw=get(api_url,{"Authorization":"Bearer "+key,"Accept":"application/json","User-Agent":"gaemiGTP-article-compare/1.0"})
data=json.loads(raw.decode("utf-8")).get("data") or {}
print("API_STATUS",status,"TITLE",data.get("title"),"PROVIDER",(data.get("provider") or {}).get("name"),flush=True)
ast=data.get("astDescription")
types=[]
def inspect(n,path="$"):
    if isinstance(n,dict):
        types.append((path,n.get("type"),list(n.keys())))
        for k,v in n.items():
            if isinstance(v,(dict,list)): inspect(v,path+"."+str(k))
    elif isinstance(n,list):
        for i,v in enumerate(n): inspect(v,path+"["+str(i)+"]")
inspect(ast)
print("AST_NODE_SHAPES",json.dumps(types[:100],ensure_ascii=False),flush=True)
def text_walk(n,out):
    if isinstance(n,dict):
        typ=n.get("type")
        if typ in ("text","plain","string") and isinstance(n.get("text"),str):
            out.append(n["text"])
        # Process child content in document order, excluding metadata/type names and href values.
        if isinstance(n.get("children"),list):
            for child in n["children"]: text_walk(child,out)
        else:
            for k in ("text","value","content"):
                v=n.get(k)
                if isinstance(v,str): out.append(v)
    elif isinstance(n,list):
        for v in n: text_walk(v,out)
    elif isinstance(n,str):
        out.append(n)
ast_parts=[]
text_walk(ast,ast_parts)
ast_text=" ".join(x for x in ast_parts if x.strip())
def norm(s):
    s=html.unescape(s)
    s=re.sub(r"<[^>]+>"," ",s)
    s=re.sub(r"\s+"," ",s).strip().lower()
    return s
print("AST_TEXT_LEN",len(ast_text),"AST_TEXT_START",repr(ast_text[:500]),flush=True)
class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth=0; self.cur=[]; self.blocks=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript","svg"): self.skip+=1
        if tag in ("p","h1","h2","h3","li"):
            if self.cur: self.blocks.append(" ".join(self.cur)); self.cur=[]
            self.depth+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg") and self.skip: self.skip-=1
        if tag in ("p","h1","h2","h3","li") and self.depth:
            if self.cur: self.blocks.append(" ".join(self.cur)); self.cur=[]
            self.depth-=1
    def handle_data(self,data):
        if not self.skip and data.strip():
            if self.depth: self.cur.append(data.strip())
def inspect_page(label,url):
    try:
        st,final,ct,b=get(url,{"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36","Accept":"text/html,application/xhtml+xml"})
        source=b.decode("utf-8","replace")
        p=ArticleParser(); p.feed(source)
        blocks=[re.sub(r"\s+"," ",x).strip() for x in p.blocks if x.strip()]
        page_text=" ".join(blocks)
        print(label+"_STATUS",st,"FINAL_URL",final,"TYPE",ct,"HTML_BYTES",len(b),"BLOCKS",len(blocks),"TEXT_LEN",len(page_text),flush=True)
        print(label+"_BLOCKS",json.dumps(blocks,ensure_ascii=False)[:12000],flush=True)
        npage=norm(page_text); nast=norm(ast_text)
        print(label+"_AST_EQUAL",npage==nast,"PAGE_CONTAINS_AST",bool(nast and nast in npage),"AST_CONTAINS_PAGE",bool(npage and npage in nast),flush=True)
        if npage and nast:
            import difflib
            sm=difflib.SequenceMatcher(None,nast,npage,autojunk=False)
            print(label+"_SIMILARITY",round(sm.ratio()*100,2),flush=True)
            print(label+"_AST_ONLY_PREFIX",repr(nast[:500]),flush=True)
            print(label+"_PAGE_ONLY_PREFIX",repr(npage[:500]),flush=True)
        return True
    except Exception as e:
        print(label+"_FETCH_ERROR",type(e).__name__,str(e)[:300],flush=True)
        return False
publisher_url=data.get("canonical_link") or data.get("link")
print("PUBLISHER_URL",publisher_url,flush=True)
if publisher_url: inspect_page("PUBLISHER",publisher_url)
inspect_page("YAHOO","https://finance.yahoo.com/markets/stocks/articles/apple-biggest-threat-isn-t-071507277.html")
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True,timeout=10).stdout.strip()=="inactive"
print("ARTICLE_COMPARE_COMPLETE_WORKER_INACTIVE",flush=True)
