import asyncio
from asyncio import StreamWriter,StreamReader
import json
import time
import uuid

from aiohttp import web,web_ws
from aiohttp import WSMsgType,web_request


from utils import (pack_data,
                   unpack_data,
                   process_publish_request,
                   process_request)

from utils import RMethod,Register,ClientConnection,SubscriptionContainer,HeartBeat

class WebServer:    
    def __init__(
        self,host:str,
        port:int,
        register:Register,
        sub_container:SubscriptionContainer,
        limitHeartbeatInterval:int = 1,
        dataCompress:bool=False)->None:
    
        self.__host = host
        self.__port = port
        self.__register = register
        self.__sub_container = sub_container
        self.__dataCompress = dataCompress
        self.__limitHeartbeatInterval = limitHeartbeatInterval


    async def start(self,loop):
        server = web.Server(self.handle_request)
        runner = web.ServerRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, self.__host, self.__port)
        await site.start()
        print(f"======= Serving on http://{site._host}:{site._port}/ ======")
        await asyncio.Future(loop=loop)
        

    async def handle_request(self,request:web_request.BaseRequest):
        """处理web请求,分发http请求和websocket请求"""
        wname = request.headers.get('Upgrade')
        if wname and wname.lower() == 'websocket':
            ws = web_ws.WebSocketResponse()            
            print(type(ws))
            await ws.prepare(request)
            await self.websocket_handler(ws)
        else:
            return await self.http_handler(request)



    async def http_handler(self,request:web_request.BaseRequest):
        """处理web请求"""        
        rm:RMethod = self.__register.methods_of_get.get(request.path)
        dicts = dict()
        execute_res:dict = dict()
        _ = request.query_string.split('&')
        status = 200
        if rm:
            for p in _:
                if '=' in p:
                    k,v = p.split('=')
                    dicts[k.strip()]=v.strip()
            execute_res = await rm.execute(args=tuple(),dicts=dicts)
            if execute_res.get('state') == 'failed': status=422
        else:
            execute_res['state'] = 'failed'
            execute_res['error'] = f'Not found!'
            status = 400
            return web.Response(status=status,text=json.dumps(execute_res),content_type='application/json')


        result = execute_res.get('result')
        if isinstance(result,web.Response):
            return result
        else:
            return web.Response(status=status,text=json.dumps(execute_res),content_type='application/json')


    async def websocket_handler(self,ws:web_ws.WebSocketResponse):
        """处理websocket请求"""
        unique_id:str = str(uuid.uuid4())
        connection = ClientConnection(unique_id,ws,self.__dataCompress)
        t = float('-inf')
        async for msg in ws:

            # 心跳检测
            if msg.type == WSMsgType.PING or msg.type == WSMsgType.TEXT and msg.data == HeartBeat.PING.value.decode():
                if time.time() - t < self.__limitHeartbeatInterval: break
                t = time.time()
                await ws.send_str(HeartBeat.PONG.value.decode())                
                continue

            if msg.type == WSMsgType.TEXT:
                try:
                    if msg.data:
                        res:dict = json.loads(msg.data)
                        if type(res)!=dict:break

                        # 处理请求
                        if await process_request(res,connection,self.__register,self.__sub_container):
                            break
                        continue
                except:
                    break

        self.__sub_container.del_sub(unique_id)
        await ws.close()
        # print('websocket connection closed.')



class Server:
    """服务端支持 jsonrpc、GET、POST、sub/pub
    Args:
        host (str): 主机地址
        port (int): 端口号
        severName (str): 服务名称
        checkParams (bool): 调用注册函数或方法时，是否检查参数类型，开启后当类型为数据模型时可以自动转换
        checkReturn (bool): 调用注册函数或方法时，是否检查返回值类型，开启后当类型为数据模型时可以自动转换
        dataMaxsize (int):  支持最大数据字节数
        limitHeartbeatInterval (int): 心跳检测的极限值，为了防止心跳攻击，默认为1s,两次心跳的间隔小于该值则会断开连接。
    """
    def __init__(
        self,host='localhost', port=8080,web_port=8081,
        *,
        severName:str='Server',
        checkParams:bool=True,
        checkReturn:bool=True,
        dataMaxsize:int=102400,
        limitHeartbeatInterval:int = 1,
        dataCompress:bool=False) -> None:
    

        self.__host = host
        self.__port = port
        self.__severName = severName
        
        self.__limitHeartbeatInterval = limitHeartbeatInterval
        self.__dataMaxsize = dataMaxsize
        self.__dataCompress = dataCompress

        
        # 实例化订阅者容器
        self.__sub_container = SubscriptionContainer()

        # 实例化注册类
        self.__register = Register(checkParams,checkReturn)

        self.__server = None
        self.__webServer = WebServer(host,web_port,self.__register,self.__sub_container,limitHeartbeatInterval,dataCompress)



    async def run(self)->None:
        """
        # 运行服务
        示例:
            ### server = Server()
            ### asyncio.run(server.run())
        """
        if self.__server!=None: return
        loop = asyncio.get_event_loop()
        async def start():            
            self.__server = await asyncio.start_server(self.__handle_client, self.__host, self.__port)
            print(f"{self.__severName} started on {self.__host}:{self.__port}")

        await asyncio.gather(start(),self.__webServer.start(loop))


    @property
    def register(self)->Register:
        """
        # 注册
        
        Returns:
            返回一个Register类的实例
        """
        return self.__register


    async def publish(self,topic:str,msg:dict)->None:
        """
        # 给指定topic推送消息
        Args:
            topic (str): 指定话题
            msg (dict): 消息
        """
        await process_publish_request(dict(topic=topic,msg=msg),self.__sub_container)
      
    
    async def __handle_client(self,reader:StreamReader, writer:StreamWriter):
        unique_id:str = str(uuid.uuid4())
        buffer = b''
        connection = ClientConnection(unique_id,writer,self.__dataCompress)
        t = float('-inf')
        while True:
            data = await reader.read(1024)
            # print(data)
            if not data:
                # 收到空消息时，退出，同时清理订阅
                break
            
            # 心跳检测            
            if data == HeartBeat.PING:
                if time.time() - t<self.__limitHeartbeatInterval:break   # 当两次心跳得时间间隔小于1s，强制断开连接。

                writer.write(HeartBeat.PONG)
                await writer.drain()
                t = time.time()
                continue

            try:
                requestName, request, buffer = unpack_data(data, buffer,self.__dataMaxsize)
                if request is None:continue
                request:bytes = request.decode('utf-8')
                res:dict = json.loads(request)
                if type(res) != dict: 
                    raise ValueError('rpc请求数据必须是dict类型')
            except Exception as e:
                # logging.log(str(e))
                break

            # 处理请求
            if await process_request(res,connection,self.__register,self.__sub_container):
                break
        
        self.__sub_container.del_sub(unique_id)
        try:
            writer.write(b'')
            await writer.drain()
            writer.close()
        except Exception as e:
            print(e)




#---------test------------
if __name__ == '__main__':
    server = Server()

    @server.register.get('/')
    async def home(name='wolrd'):
        return web.Response(text=f"<h3 style ='color: orange;'> Hello {name}.</h3>",content_type='text/html')
    
    @server.register.rpc
    @server.register.get()
    async def add(a:int,b:int):
        return a+b
    
    @server.register.rpc
    @server.register.get()
    async def add2(d:dict):
        return d['a']+d['b']
    
    @server.register.rpc
    @server.register.get()
    async def add3(l:list):
        return l[0]+l[1]
    

    asyncio.run(server.run())