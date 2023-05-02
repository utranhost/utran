
import asyncio
from concurrent.futures import ProcessPoolExecutor
import time
import aiohttp
import ujson
import re
from aiohttp import web
from aiohttp.web import Response as HttpResponse
from aiohttp.web_ws import WebSocketResponse
from aiohttp import WSMsgType,web_request
from utran.handler import process_request
from utran.object import HeartBeat, UtRequest, UtState, create_UtRequest

from utran.register import RMethod, Register
from utran.object import ClientConnection, SubscriptionContainer
from utran.server.baseServer import BaseServer
from utran.log import logger



class WebServer(BaseServer):
    __slots__=('__auth',)

    def __init__(self, 
                 *, 
                 register: Register = None, 
                 sub_container: SubscriptionContainer = None, 
                 severName: str = 'WebServer', 
                 checkParams: bool = True, 
                 checkReturn: bool = True, 
                 dataMaxsize: int = 1024**2*10,   # 默认最大支持10M的数据传输
                 limitHeartbeatInterval: int = 1, 
                 dataEncrypt: bool = False, 
                 workers: int = 0, 
                 pool:ProcessPoolExecutor=None) -> None:
        super().__init__(
            register=register, 
            sub_container=sub_container, 
            severName=severName, 
            checkParams=checkParams, 
            checkReturn=checkReturn, 
            dataMaxsize=dataMaxsize, 
            limitHeartbeatInterval=limitHeartbeatInterval, 
            dataEncrypt=dataEncrypt, 
            workers=workers, 
            pool=pool)
        
        self.__auth:aiohttp.BasicAuth = aiohttp.BasicAuth('utranhost','utranhost')


    async def start(self,host: str,port: int,username:str=None,password:str=None) -> None:
        self._host = host
        self._port = port
        if username!=None or password!=None:
            assert username!=None,'username is None.'
            assert password!=None,'password is None.'
            self.__auth:aiohttp.BasicAuth = aiohttp.BasicAuth(username,password)

        # 创建进程池
        if self._workers>0 and self._pool is None:
            self._pool = ProcessPoolExecutor(self._workers)
            
        server = web.Server(self.handle_request)
        runner = web.ServerRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        logger.success(f"\n{'='*6} {self._severName} on http://{site._host}:{site._port}/ {'='*6}")
        await self._exitEvent.wait()
        

    async def handle_request(self,request:web_request.BaseRequest):
        """处理web请求,分发http请求和websocket请求"""

        wname = request.headers.get('Upgrade')
        if wname and wname.lower() == 'websocket':         
            # 验证身份验证信息
            ticket = request.query.get('ticket')
            auth_header = request.headers.get('Authorization')
            
            ws = WebSocketResponse(max_msg_size=self._dataMaxsize)
            await ws.prepare(request)  

            auth_64 = auth_header or ticket
            if auth_64:
                if not await self.auth_connect(ws,auth_64):
                    await ws.close()
                    return
                isAuth = False
            else:
                isAuth = True

            await self.websocket_handler(ws,isAuth)
        else:
            return await self.http_handler(request)


    async def auth_connect(self,ws:WebSocketResponse,auth_64:str):
        try:
            auth = self.__auth.decode(auth_64)
        except:
            await ws.send_str('身份验证失败!')
            return False
        
        if auth == self.__auth:
            await ws.send_bytes(b'ok')
            return True
        else:
            await ws.send_str('身份验证失败!')
            return False

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
            state,result,error = await rm.execute(args=tuple(),dicts=dicts,pool=self._pool)
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


    async def websocket_handler(self,ws:WebSocketResponse,isAuth:bool=True):
        """处理websocket请求
        isAuth 是否需要身份验证
        """
        connection = ClientConnection(ws,self._dataEncrypt)
        t = float('-inf')
        async for msg in ws:
            # 心跳检测
            if msg.type == WSMsgType.PING:
                if time.time() - t < self._limitHeartbeatInterval: break
                t = time.time()
                await ws.send_str(HeartBeat.PONG.value.decode())                
                continue

            # 首次身份验证
            if isAuth:
                try:
                    auth_64 = ujson.loads(msg.data)
                    await self.auth_connect(ws,auth_64)
                except:
                    await self.auth_connect(ws,'')
                    break

            # 请求处理
            if msg.type == WSMsgType.TEXT or msg.type == WSMsgType.BINARY:
                try:
                    if msg.data:
                        res:dict = ujson.loads(msg.data)
                        if type(res)!=dict:break
                        # 处理请求
                        asyncio.create_task(process_request(create_UtRequest(res,res.get('id'),res.get('encrypt')),connection,self._register,self._sub_container,pool=self._pool))
                        continue
                except:
                    break

        connection.close()
        self._sub_container.del_sub(connection.id)
        await ws.close()
        # print('websocket connection closed.')