import asyncio
from typing import Coroutine, Union
from utran.client.baseclient import BaseClient
from utran.utils import parse_utran_uri

class ExeProxy:
    """远程执行代理"""
    
    def __init__(self,accessProxy:'AccessProxy'):
        self._loop_ = asyncio.get_event_loop()
        self._accessProxy_ = accessProxy

    def __getattr__(self, methodName):
        """类的访问"""
        self._accessProxy_.__getattr__(self._accessProxy_._temp_name_+'.'+methodName)
        return self
    
    def __call__(self, *args: any, **dicts: any) -> any:
        """执行远程函数"""
        f = self._accessProxy_._bsclient_.call(methodName=self._accessProxy_._temp_name_,args=args,dicts=dicts,**self._accessProxy_._temp_opts_)
        if self._accessProxy_._bsclient_._isRuning:
            return asyncio.create_task(f)
        else:
            if self._accessProxy_._temp_opts_.get('multicall'):
                return f
            else:
                res = self._loop_.run_until_complete(self._accessProxy_._bsclient_.start(main=f))
                return res


class AccessProxy:
    """访问代理"""
    def __init__(self,bsclient:BaseClient):
        self._temp_opts_ = dict()
        self._temp_name_:str = ''
        self._bsclient_ = bsclient
        self._exeProxy_ = ExeProxy(self)

    def __getattr__(self, methodName):
        self._temp_name_ = methodName
        return self._exeProxy_


    def __call__(self,*,timeout:int=None,encrypt:bool=None, ignore:bool=None,multicall:bool=False):
        """# 设置调用选项
        Args:
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒） ，默认为为client实例化的值
            encrypt: 是否加密， 默认为为client实例化的值
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充，默认为为client实例化的值
            multicall: 是否标记为合并调用
        """
        self._temp_opts_ = dict(timeout= self._bsclient_._localTimeout if timeout==None else timeout,
                          encrypt= self._bsclient_._encrypt if timeout==None else encrypt,
                          ignore = self._bsclient_._ignore if ignore==None else ignore,
                          multicall = multicall)
        return self


class Client:
    """# 客户端
    支持代理调用
    Args:
        heartbeatFreq: 心跳频率
        serverTimeout: 服务器心跳响应超时时间，用于判断是否断线，超过此值会进行重连 (单位:秒)
        localTimeout: 本地调用超时 (单位:秒)
        reconnectNum: 断线重连的次数
        ignore: 是否忽略远程调用异常
        encrypt: 是否加密传输
    """
    __slots__ = ('_localTimeout','_ignore','_encrypt','_heartbeatFreq','_serverTimeout','_reconnectNum','_bsclient','_proxy','_serveHost','_servePort')
    def __init__(self,
                 *,
                 host:str=None,
                 port:int=None,
                 uri:str = None,
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

        self._serveHost:str = host                                      # 服务器host 
        self._servePort:int = port                                      # 服务器端口号

        if uri:
            self._serveHost,self._servePort = parse_utran_uri(uri)

        # 基础客户端
        self._bsclient:BaseClient = BaseClient(heartbeatFreq=heartbeatFreq,
                                               serverTimeout=serverTimeout,
                                               reconnectNum=reconnectNum,
                                               encrypt=encrypt,
                                               host=self._serveHost,
                                               port=self._servePort)

        self._proxy = AccessProxy(self._bsclient)
        

    def __call__(self, *args: any,**opts: any) -> callable:
        """指定入口函数，可以使用装饰器方式指定入口函数"""
        return self._bsclient(*args,**opts)
    

    async def start(self,main:Union[asyncio.Future,Coroutine]=None,uri:str=None,host:str=None,port:int=None):
        host = host or self._serveHost
        port = port or self._servePort
        await self._bsclient.start(main=main,uri=uri,host=host,port=port)

    @property
    def subscribe(self)->BaseClient.subscribe:
        """订阅
        异步方法
        Returns:
            返回订阅方法
        """
        return self._bsclient.subscribe
    

    @property
    def unsubscribe(self)->BaseClient.unsubscribe:
        """订阅
        异步方法
        Returns:
            返回取消订阅方法
        """
        return self._bsclient.unsubscribe
    

    def multicall(self,*calls:Coroutine,encrypt:bool = False,timeout:int=None,ignore:bool=None)->list:
        """# 合并多次调用远程方法或函数
        支持同步和异步的调用，
                同步调用方式会：1自动建立连接 -- 2任务执行完毕 --3自动关闭连接，适用于未建立连接时使用。
                异步调用方式会：1使用现有的连接-- 2任务执行完毕。适用于已建立连接时。
        Args:
            *calls: 需要远程调用协程对象
            encrypt: 是否加密
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
        
        Returns:
            执行结果按顺序放在列表中返回
        """
        f = self._bsclient.multicall(*calls,encrypt=encrypt,timeout=timeout,ignore=ignore)        
        if self._bsclient._isRuning:
            return f
        else:
            _loop = asyncio.get_event_loop()
            return _loop.run_until_complete(self._bsclient.start(main=f))


    @property
    def call(self)->AccessProxy:
        """远程调用
        支持同步和异步的调用，
                同步调用方式会：1自动建立连接 -- 2任务执行完毕 --3自动关闭连接，适用于未建立连接时使用。
                异步调用方式会：1使用现有的连接-- 2任务执行完毕。适用于已建立连接时。

        Returns:
            返回远程调用的代理类
        """
        return self._proxy
        