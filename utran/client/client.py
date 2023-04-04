import asyncio
from typing import Coroutine, Union
from utran.client.baseclient import BaseClient



class RPCProxy:
    """代理远程调用"""
    def __init__(self,bsclient:BaseClient):
        self._opts = dict()
        self._bsclient = bsclient

    def __getattr__(self, methodname):
        def wrapper(*args, **dicts):     
            return asyncio.create_task(self._bsclient.call(methodname,args=args,dicts=dicts,**self._opts))
        return wrapper


    def __call__(self,*,timeout:int=None,encrypt:bool=None, ignore:bool=None,multicall:bool=False):
        """# 设置调用选项
        Args:
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒） ，默认为为client实例化的值
            encrypt: 是否加密， 默认为为client实例化的值
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充，默认为为client实例化的值
            multicall: 是否标记为合并调用
        """
        self._opts = dict(timeout= self._bsclient._localTimeout if timeout==None else timeout,
                          encrypt= self._bsclient._encrypt if timeout==None else encrypt,
                          ignore = self._bsclient._ignore if ignore==None else ignore,
                          multicall = multicall)
        return self


class Client:
    """# 客户端
    支持代理调用
    Args:
        heartbeatFreq: 心跳频率
        serverTimeout: 服务器响应超时时间，用于判断是否断线，超过此值会进行重连 (单位:秒)
        localTimeout: 本地调用超时 (单位:秒)
        reconnectNum: 断线重连的次数
        ignore: 是否忽略远程调用异常
        encrypt: 是否加密传输
    """
    __slots__ = ('_localTimeout','_ignore','_encrypt','_heartbeatFreq','_serverTimeout','_reconnectNum','_bsclient','_proxy')
    def __init__(self,
                 *,
                 heartbeatFreq:int=2,
                 serverTimeout:int=2,
                 localTimeout:int=5,
                 reconnectNum:int=32,
                 ignore:bool = False,
                 encrypt: bool = False) -> None:
        
        self._ignore = ignore
        self._localTimeout:int= localTimeout
        self._encrypt:bool = encrypt                                    # 是否加密
        self._heartbeatFreq:int = heartbeatFreq                         # 心跳频率（单位：秒）
        self._serverTimeout:int = serverTimeout                         # 服务器响应超时时间 （单位：秒）
        self._reconnectNum:int = reconnectNum                           # 断线重连的次数

        # 基础客户端
        self._bsclient:BaseClient = BaseClient(heartbeatFreq=heartbeatFreq,
                                               serverTimeout=serverTimeout,
                                               reconnectNum=reconnectNum,
                                               encrypt=encrypt)

        self._proxy = RPCProxy(self._bsclient)


    def __call__(self, *args: any,**opts: any) -> callable:
        return self._bsclient(*args,**opts)
    
    async def start(self,main:Union[asyncio.Future,Coroutine]=None,uri:str=None,host:str=None,port:int=None):
        await self._bsclient.start(main=main,uri=uri,host=host,port=port)

    @property
    def subscribe(self)->BaseClient.subscribe:
        """订阅
        Returns:
            返回订阅方法
        """
        return self._bsclient.subscribe
    

    @property
    def unsubscribe(self)->BaseClient.unsubscribe:
        """订阅
        Returns:
            返回取消订阅方法
        """
        return self._bsclient.unsubscribe
    

    @property
    def multicall(self)->BaseClient.multicall:
        """合并多次调用
        Returns:
            返回合并调用的方法
        """
        return self._bsclient.multicall

    @property
    def call(self)->RPCProxy:
        """远程调用
        Returns:
            返回远程调用的方法
        """
        return self._proxy
        