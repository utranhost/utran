
from abc import ABC,abstractmethod
import asyncio
from asyncio import Future,coroutine
from typing import Union
import ujson
from utran.client.que import ResultQueue
from utran.object import UtResponse, UtType
from utran.utils import gen_utran_request, parse_utran_uri, unpack_data2_utran



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
        self._reslutqueue = reslutqueue or ResultQueue()
        self._encrypt = encrypt
        self._buffer = b''


    async def run(self,uri:str,coros_or_futures:Union[Future,coroutine]):
        """启动连接"""
        serveHost,servePort = parse_utran_uri(uri)
        self._reader, self._writer = await asyncio.open_connection(serveHost, servePort)

        receive_task = asyncio.create_task(self.__receive())
        main_task = asyncio.create_task(coros_or_futures)
 
        if not await main_task:
            receive_task.cancel()
            await self.close()


    async def call(self,methodName,*args,**dicts)->UtResponse:
        requestId,request_packet = gen_utran_request(UtType.RPC,self._encrypt,methodName=methodName,args=args,dicts=dicts)
        self._writer.write(request_packet)
        await self._writer.drain()

        while True:
            response = self._reslutqueue.pull(requestId)
            if response:
                return response
            await asyncio.sleep(0)


    async def __receive(self):
        while True:
            chunk = await self._reader.read(1024)
            if not chunk:
                raise ConnectionError('Connection closed by server')
            name,message,self._buffer = unpack_data2_utran(chunk, self._buffer)
            if message is not None:
                response:UtResponse = UtResponse(**ujson.loads(message.decode('utf-8').strip()))
                self._reslutqueue.push(response)


    async def close(self):
        """关闭连接"""
        self._writer.write(b'')
        await self._writer.drain()
        self._writer.close()
        self._reader = None
        self._writer = None


def run(main:coroutine):
    asyncio.run(main)