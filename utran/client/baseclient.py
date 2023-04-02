
from functools import partial
from abc import ABC,abstractmethod
import asyncio
from asyncio import Future,coroutine,Task
from typing import Union
import ujson
from utran.client.que import ResultQueue
from utran.object import UtRequest, UtResponse, UtType, create_UtRequest
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


class Client:

    def __init__(self,reslutqueue:ResultQueue=None,encrypt: bool = False) -> None:
        self._reader = None
        self._writer = None
        self._reslutqueue:ResultQueue = reslutqueue or ResultQueue()
        self._encrypt = encrypt
        self._buffer = b''
        self._lock = asyncio.Lock()
        self._single_semaphore = asyncio.Semaphore(1)

    async def run(self,uri:str,coros_or_futures:Union[Future,coroutine]):
        """启动连接"""
        serveHost,servePort = parse_utran_uri(uri)
        self._reader, self._writer = await asyncio.open_connection(serveHost, servePort)
        
        main_task = asyncio.create_task(coros_or_futures)
        receive_task = asyncio.create_task(self.__receive())
 
        if not await main_task:
            receive_task.cancel()
            await self.close()


    async def rpccall(self,methodName:str,*,args:list=tuple(),dicts:dict=dict(),timeout:int=30,multicall:bool=False,encrypt=None)->UtResponse:
        return await self.call(UtType.RPC,methodName,args,dicts,timeout=timeout,multicall=multicall,encrypt=encrypt)


    async def call(self,requestType:UtType,methodName:str,args:list,dicts:dict,*,timeout:int=30,multicall:bool=False,encrypt=None)->Union[UtResponse,dict]:
        """# 单次调用远程方法或函数"""
        msg = dict(requestType=requestType.value,methodName=methodName,args=args,dicts=dicts)
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


    async def _send(self,request:UtRequest,timeout:int=None):
        async with self._single_semaphore:     # 每次只允许一个协程调用call方法     
            self._writer.write(request.pick_utran_request())
            await self._writer.drain()

            e = asyncio.Event()
            self._reslutqueue.push_event(request.id,e)
            try:
                await asyncio.wait_for(e.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError('Request timed out')            

            response:UtResponse = self._reslutqueue.pull(request.id)
            return response.result


    async def __receive(self):
        while True:
            chunk = await self._reader.read(1024)
            if not chunk:
                raise ConnectionError('Connection closed by server')
            name,message,self._buffer = unpack_data2_utran(chunk, self._buffer)
            if message is not None:
                response:UtResponse = UtResponse(**ujson.loads(message.decode('utf-8').strip()))
                self._reslutqueue.push(response)
                e:asyncio.Event = self._reslutqueue.pull_event(response.id)
                if e:e.set()


    async def close(self):
        """关闭连接"""
        self._writer.write(b'')
        await self._writer.drain()
        self._writer.close()
        self._reader = None
        self._writer = None


def run(main:coroutine):
    asyncio.run(main)