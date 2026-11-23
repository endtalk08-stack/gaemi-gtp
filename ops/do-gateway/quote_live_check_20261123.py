import base64
import json
import os
import socket
import ssl
import struct
import time
from urllib.request import urlopen

ctx = ssl._create_unverified_context()
with urlopen('http://127.0.0.1:8765/health', timeout=5) as reply:
    print('LOCAL_HEALTH', reply.status, flush=True)
raw = socket.create_connection(('127.0.0.1', 443), timeout=8)
sock = ctx.wrap_socket(raw, server_hostname='quotes.gaemigtp.com')
sock.settimeout(8)
key = base64.b64encode(os.urandom(16)).decode()
request = ('GET /ws/us-live-quotes HTTP/1.1\r\nHost: quotes.gaemigtp.com\r\n'
           'Origin: https://gaemigtp-main.pages.dev\r\nUpgrade: websocket\r\n'
           'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
           'Sec-WebSocket-Key: ' + key + '\r\n\r\n')
sock.sendall(request.encode())
response = b''
while b'\r\n\r\n' not in response:
    response += sock.recv(4096)
header, payload = response.split(b'\r\n\r\n', 1)
print('WEBSOCKET_UPGRADE', header.split(b'\r\n', 1)[0].decode(), flush=True)
for _ in range(30):
    while len(payload) < 2:
        payload += sock.recv(4096)
    size = payload[1] & 127
    head = 2
    if size == 126:
        while len(payload) < 4:
            payload += sock.recv(4096)
        size = struct.unpack('!H', payload[2:4])[0]
        head = 4
    elif size == 127:
        while len(payload) < 10:
            payload += sock.recv(4096)
        size = struct.unpack('!Q', payload[2:10])[0]
        head = 10
    while len(payload) < head + size:
        payload += sock.recv(4096)
    message = json.loads(payload[head:head + size])
    payload = payload[head + size:]
    selected = [item for item in ([message.get('quote')] if message.get('type') == 'quote' else message.get('items') or [])
                if item and item.get('symbol') in ('QQQ', 'NVDA', 'XLK', 'SPY', 'DIA')]
    print('FRAME', message.get('type'), [(x.get('symbol'), x.get('price'), x.get('change_pct'),
           x.get('reference_close_date'), x.get('stale')) for x in selected], flush=True)
sock.close()
