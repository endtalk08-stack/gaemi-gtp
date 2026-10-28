import pathlib,base64,json,hashlib
base=pathlib.Path('/opt/gaemigtp-news/app')
for rel in ['backend/services/news_processed_store.py','backend/services/news_result.py','backend/news_worker.py']:
 data=(base/rel).read_bytes()
 print('EGRESS_SOURCE='+json.dumps({'path':rel,'sha256':hashlib.sha256(data).hexdigest(),'base64':base64.b64encode(data).decode()}),flush=True)
