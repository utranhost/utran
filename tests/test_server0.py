import aiohttp
import asyncio
from aiohttp.web import Application,WebSocketResponse,run_app,get,Server,ServerRunner,TCPSite

__auth = aiohttp.BasicAuth('utranhost','utranhost')

async def handle(request):
    auth_header = request.headers.get('Authorization') or request.query.get('Authorization')
    if auth_header:
        auth = __auth.decode(auth_header)
    else:            
        auth = None

    ws = WebSocketResponse(max_msg_size=1024**2*500)
    await ws.prepare(request)
    if auth != __auth:
        # 身份验证失败
        await ws.send_str('身份验证失败!')
        return
    else:
        #  身份验证成功
        await ws.send_str('ok')

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            await ws.send_str('Hello, ' + msg.data)
        elif msg.type == aiohttp.WSMsgType.BINARY:
            await ws.send_bytes(msg.data)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print('ws connection closed with exception %s' %
                  ws.exception())

    return ws

# app = Application()
# app.add_routes([get('/', handle)])


async def run():
    host='127.0.0.1'
    port=9990
    server = Server(handle)
    runner = ServerRunner(server)
    await runner.setup()
    site = TCPSite(runner, host, port)
    await site.start()
    print(f"\n{'='*6} runing on http://{site._host}:{site._port}/ {'='*6}")
    await asyncio.Future()

if __name__ == '__main__':
    # run_app(app,host='127.0.0.1',port=9990)
    asyncio.run(run())