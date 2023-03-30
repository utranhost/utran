
import asyncio
import time
import ujson
import re
from aiohttp import web
from aiohttp.web import Response as HttpResponse
from aiohttp.web_ws import WebSocketResponse
from aiohttp import WSMsgType,web_request
from utran.handler import process_request
from utran.object import HeartBeat, UtState

from utran.register import RMethod, Register
from utran.utils import ClientConnection, SubscriptionContainer
from utran.server.baseServer import BaseServer



class WebServer(BaseServer):
    __slots__=tuple()
    def __init__(
            self,
            host: str,
            port: int,
            *,
            register: Register = None,
            sub_container: SubscriptionContainer = None,
            severName: str = 'WebServer',
            dataMaxsize: int = 102400,
            limitHeartbeatInterval: int = 1,
            dataEncrypt: bool = False) -> None:
        
        super().__init__(
            host,
            port,
            register=register, 
            sub_container=sub_container, 
            severName=severName, 
            dataMaxsize=dataMaxsize, 
            limitHeartbeatInterval=limitHeartbeatInterval, 
            dataEncrypt=dataEncrypt)


    async def start(self):
        server = web.Server(self.handle_request)
        runner = web.ServerRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        print(f"{'='*6} {self._severName} on http://{site._host}:{site._port}/ {'='*6}")
        loop = asyncio.get_event_loop()
        await asyncio.Future(loop=loop)
        

    async def handle_request(self,request:web_request.BaseRequest):
        """处理web请求,分发http请求和websocket请求"""
        wname = request.headers.get('Upgrade')
        if wname and wname.lower() == 'websocket':
            ws = WebSocketResponse()            
            print(type(ws))
            await ws.prepare(request)
            await self.websocket_handler(ws)
        else:
            return await self.http_handler(request)



    async def http_handler(self,request:web_request.BaseRequest):
        """处理web请求""" 
        execute_res:dict = dict()

        if request.method not in [ 'GET', 'POST']:
            execute_res['state'] = 'failed'
            execute_res['error'] = f'Method that is not allowed by the server'
            status = 500
            return HttpResponse(status=status,text=ujson.dumps(execute_res),content_type='application/json')
    
        if request.method == 'GET':
            rm:RMethod = self._register.methods_of_get.get(request.path)
        else:
            rm:RMethod = self._register.methods_of_post.get(request.path)

            
        _ = request.query_string.split('&')
        status = 200
        if rm:
            dicts = dict()
            for p in _:
                if '=' in p:
                    k,v = re.split(r"=", p, maxsplit=1)
                    dicts[k.strip()]=v.strip()
            state,result,error = await rm.execute(args=tuple(),dicts=dicts)
            execute_res['state'] = state.value
            execute_res['error'] = error
            execute_res['result'] = result
            if state == UtState.FAILED:
                status=422
        else:
            execute_res['state'] = 'failed'
            execute_res['error'] = f'Not found!'
            status = 400
            return HttpResponse(status=status,text=ujson.dumps(execute_res),content_type='application/json')

        if isinstance(result,HttpResponse):
            return result
        else:
            return HttpResponse(status=status,text=ujson.dumps(execute_res),content_type='application/json')


    async def websocket_handler(self,ws:WebSocketResponse):
        """处理websocket请求"""
        connection = ClientConnection(ws,self._dataEncrypt)
        t = float('-inf')
        async for msg in ws:

            # 心跳检测
            if msg.type == WSMsgType.PING or msg.type == WSMsgType.TEXT and msg.data == HeartBeat.PING.value.decode():
                if time.time() - t < self._limitHeartbeatInterval: break
                t = time.time()
                await ws.send_str(HeartBeat.PONG.value.decode())                
                continue

            if msg.type == WSMsgType.TEXT:
                try:
                    if msg.data:
                        res:dict = ujson.loads(msg.data)
                        if type(res)!=dict:break

                        # 处理请求
                        if await process_request(res,connection,self._register,self._sub_container):
                            break
                        continue
                except:
                    break

        self._sub_container.del_sub(connection.id)
        await ws.close()
        # print('websocket connection closed.')