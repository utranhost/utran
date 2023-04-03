
from functools import partial
from abc import ABC,abstractmethod
import asyncio
from asyncio import Future,coroutine
import inspect

from typing import Union,Callable
import ujson
from utran.log import logger
from utran.client.que import ResultQueue
from utran.object import UtRequest, UtResponse, UtType, create_UtRequest,HeartBeat
from utran.utils import parse_utran_uri, unpack_data2_utran


class BaseClient(ABC):
    """#客户端基类
    utran://host:port
    """
    __slots__=('_serveHost','_servePort','_reslutqueue','_isconnected','_buffer','_encrypt')

    def __init__(self,uri:str,reslutqueue:ResultQueue=None,encrypt: bool = False) -> None:
        self._serveHost,self._servePort = parse_utran_uri(uri)
        self._reslutqueue = reslutqueue or ResultQueue()
        self._encrypt = encrypt
        self._isconnected=False
        self._buffer = b''


    @abstractmethod
    def subscribe(self,topic:str,callback:callable):
        """订阅"""

    @abstractmethod
    def unsubscribe(self,topics:list[str]):
        """取消订阅"""

    @abstractmethod
    def call(self,method_name,*args,**dicts):
        """调用远程方法或函数"""

    @abstractmethod
    def connect(self):
        """连接服务器"""

    @abstractmethod        
    def close(self):
        """关闭连接"""


class HeartBeatTimer:
    def __init__(self,
                 ping_sender:Callable,
                 timeout_callback:Callable,
                 ping_freq:int=2,
                 pong_timeout:int=2,
                 ) -> None:
        
        self._ping_freq = ping_freq
        self._pong_timeout = pong_timeout
        self._pingTask:asyncio.Task = None
        self._timeoutTask:asyncio.Task = None
        self._ping_sender =ping_sender
        self._timeout_callback = timeout_callback

    def ping(self):
        if self._timeoutTask:
            self._timeoutTask.cancel()

        if self._pingTask and not self._pingTask.done():
            self._pingTask.cancel()
        self._pingTask = asyncio.create_task(self.__ping())        

    async def __timeout(self):
        # print("创建超时任务")
        try:
            await asyncio.sleep(self._pong_timeout)
            if inspect.iscoroutinefunction(self._timeout_callback):
                await self._timeout_callback()
            else:
                self._timeout_callback()
        except asyncio.CancelledError:
            # print("超时任务被取消")
            pass

    async def __ping(self):        
        await asyncio.sleep(self._ping_freq)
        if inspect.iscoroutinefunction(self._ping_sender):
            await self._ping_sender()
        else:
            self._ping_sender()
        print("PING")
        self._timeoutTask = asyncio.create_task(self.__timeout())
        


class Client:

    def __init__(self,reslutqueue:ResultQueue=None,encrypt: bool = False,heartbeatFreq:int=2,serverTimeout:int=2) -> None:
        self._reader = None
        self._writer = None
        self._reslutqueue:ResultQueue = reslutqueue or ResultQueue()
        self._encrypt = encrypt
        self._buffer = b''
        self._lock = asyncio.Lock()
        self._single_semaphore = asyncio.Semaphore(1)
        self._topics_handler = dict()
        self._exitEvent = asyncio.Event()
        self._heartbeatFreq = heartbeatFreq
        self._serverTimeout = serverTimeout
        self._heartbeatTimer = None


    async def run(self,uri:str,coros_or_futures:Union[Future,coroutine]):
        """启动连接"""
        serveHost,servePort = parse_utran_uri(uri)
        self._reader, self._writer = await asyncio.open_connection(serveHost, servePort)
                
        main_task = asyncio.create_task(coros_or_futures)
        receive_task = asyncio.create_task(self.__receive())
        # await main_task
        
        async def to_ping():await self._send(None,heartbeat=True)
        async def pong_timeout():
            logger.error("服务器无响应，程序退出")
            await self.exit()
        self._heartbeatTimer = self._heartbeatTimer or HeartBeatTimer(to_ping,pong_timeout,self._heartbeatFreq,self._serverTimeout)
        self._heartbeatTimer.ping()

        await self._exitEvent.wait()
        receive_task.cancel()
        await self._close()


    async def subscribe(self,
                        topic:Union[str,tuple[str]],
                        callback:callable,
                        *,
                        timeout:int=30)->Union[UtResponse,dict]:
        """订阅
        Attributes:
            id (int): 请求体id
            requestType (str): 标记请求类型
            topics (Tuple[str]): 可以同时订阅一个或多个话题
        """

        if type(topic) in [list,tuple]:
            for t in topic:
                if type(t)==str: self._topics_handler[t] = callback
                else: raise ValueError(f'"{t}" must be a string!')
        elif type(topic)==str:
            self._topics_handler[topic] = callback
        else:
            raise ValueError(f'"{topic}" must be a str or List[str] !')

        msg = dict(requestType=UtType.SUBSCRIBE.value,topics=topic)
        request:UtRequest = create_UtRequest(msg)
        return await self._send(request,timeout)
        

    async def unsubscribe(self,
                          topic:Union[str,tuple[str]],
                          *,
                          timeout:int=30)->Union[UtResponse,dict]:
        """取消订阅"""
        if type(topic) in [list,tuple]: [self._topics_handler.pop(t) for t in topic]              
        elif type(topic)==str:self._topics_handler.pop(topic)
        else:raise ValueError(f'"{topic}" must be a str or List[str] !')

        msg = dict(requestType=UtType.SUBSCRIBE.value,topics=topic)
        request:UtRequest = create_UtRequest(msg)
        return await self._send(request,timeout)
        

    async def call(self,
                   methodName:str,
                   args:list=tuple(),
                   dicts:dict=dict(),
                   *,
                   timeout:int=30,
                   multicall:bool=False,
                   encrypt=None)->Union[UtResponse,dict]:
        """# 调用远程方法或函数
        Args:
            methodName: 远程的方法或函数的名称
            args: 列表参数
            dicts: 字典参数
            timeout: 超时设置
            multicall: 是否标记为合并调用
            encrypt: 是否加密
        """
        msg = dict(requestType=UtType.RPC.value,methodName=methodName,args=args,dicts=dicts)
        if multicall:
            return msg
        else:
            encrypt = self._encrypt if encrypt==None else encrypt
            request:UtRequest = create_UtRequest(msg,encrypt=encrypt)
            return await self._send(request,timeout)
        

    async def multicall(self,*calls,encrypt:bool = False,timeout:int=30):
        """# 合并多次调用远程方法或函数"""
        msgs = await asyncio.gather(*calls)
        encrypt = self._encrypt if encrypt==None else encrypt
        request:UtRequest = create_UtRequest(dict(requestType=UtType.MULTICALL,multiple=msgs),encrypt=encrypt)
        return await self._send(request,timeout)


    async def _send(self,request:UtRequest,timeout:int=None,heartbeat:bool=False):
        async with self._single_semaphore:     # 每次只允许一个协程调用call方法    
            if heartbeat:
                self._writer.write(HeartBeat.PING.value)
                await self._writer.drain()
                return
             
            self._writer.write(request.pick_utran_request())
            await self._writer.drain()

            response:UtResponse = await self._reslutqueue.wait_response(request,timeout=timeout)
            return response.result


    async def __receive(self):
        while True:
            chunk = await self._reader.read(1024)
            if not chunk:
                raise ConnectionError('Connection closed by server')
            # 心跳检测
            self._heartbeatTimer.ping()
            if chunk == HeartBeat.PONG.value:
                print("PONG")
                continue
            name,message,self._buffer = unpack_data2_utran(chunk, self._buffer)
            if message is not None:
                try:
                    name:str = name.decode('utf-8')
                    response:UtResponse = UtResponse(**ujson.loads(message.decode('utf-8').strip()))
                except Exception as e:
                    logger.warning(f'服务器消息异常: {e}')
                    continue
                if name == UtType.PUBLISH.value:
                    asyncio.create_task(self._handler_publish(response))
                else:
                    self._reslutqueue.cache_response(response)
   


    async def _handler_publish(self,response:UtResponse):
        """处理话题推流"""
        print(response.to_dict())


    async def _close(self):
        """关闭连接"""
        try:
            self._writer.write(b'')
            await self._writer.drain()
        except:
            pass
        self._writer.close()
        self._reader = None
        self._writer = None

    async def exit(self):
        self._exitEvent.set()


def run(main:coroutine):
    asyncio.run(main)