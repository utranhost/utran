import asyncio
from asyncio import Future
from functools import partial
import threading
import time
from typing import Callable, Coroutine, Union
from utran.client.baseclient import BaseClient
from utran.utils import parse_utran_uri
import inspect

class ExeProxy:
    """远程执行代理"""
    __slots__ = ('_accessProxy_',)
    def __init__(self,accessProxy:'AccessProxy'):
        self._accessProxy_ = accessProxy

    def __getattr__(self, methodName):
        """类的访问"""
        self._accessProxy_.__getattr__(self._accessProxy_._temp_name_+'.'+methodName)
        return self
    
    def __call__(self, *args: any, **dicts: any) -> Union[any,asyncio.Task,dict]:
        """# 执行远程函数

        Returns:
            返回值 (dict): 当选项标记为multicall时: `client.call(multicall=True).add(1,2)`         
            返回值 (asyncio.Task): 当baseclient已经运行时，`client.call.add(1,2)` 返回Task。可使用await拿到调用结果，例: `await client.call.add(1,2)`
            返回值 (any): 当baseclient未运行时，`client.call.add(1,2)`返回最终的调用结果
        """
        f:Union[Coroutine,dict] = self._accessProxy_._client_._bsclient.call(methodName=self._accessProxy_._temp_name_,args=args,dicts=dicts,**self._accessProxy_._temp_opts_)
        
        if self._accessProxy_._client_._enterLoop:
            # self._accessProxy_._client_._enterLoop.run_until_complete
            futrue = asyncio.run_coroutine_threadsafe(f,self._accessProxy_._client_._enterLoop)
            return futrue.result()

        if self._accessProxy_._client_._bsclient._isRuning:
            # f is coroutine
            return asyncio.create_task(f)
        else: 
            if self._accessProxy_._temp_opts_.get('multicall'):
                # f is dict
                return f
            else:
                # f is coroutine
                loop = asyncio.get_event_loop()
                res = loop.run_until_complete(self._accessProxy_._client_._bsclient.start(main=f))
                return res

class AccessProxy:
    """访问代理"""
    __slots__ = ('_temp_opts_','_temp_name_','_client_','_exeProxy_')
    def __init__(self,client:'Client'):
        self._temp_opts_ = dict()
        self._temp_name_:str = ''
        self._client_ = client
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
        self._temp_opts_ = dict(timeout= self._client_._localTimeout if timeout==None else timeout,
                          encrypt= self._client_._encrypt if timeout==None else encrypt,
                          ignore = self._client_._ignore if ignore==None else ignore,
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
    __slots__ = ('_localTimeout','_ignore','_encrypt','_heartbeatFreq','_serverTimeout','_reconnectNum','_bsclient','_proxy','_serveHost','_servePort','_enterLoop','_thread')
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
        self._bsclient:BaseClient = None

        self._enterLoop:asyncio.AbstractEventLoop = None                # 使用__enter__时创建的loop

        if uri:
            self._serveHost,self._servePort = parse_utran_uri(uri)


        self._bsclient:BaseClient = BaseClient(heartbeatFreq=self._heartbeatFreq,
                                                serverTimeout=self._serverTimeout,
                                                reconnectNum=self._reconnectNum,
                                                encrypt=self._encrypt,
                                                host=self._serveHost,
                                                port=self._servePort)
        self._proxy = AccessProxy(self)


    def __call__(self, *args: any,**opts: any) -> callable:
        """指定入口函数，可以使用装饰器方式指定入口函数"""
        if len(args)==0:
            return partial(self.__call__,**opts)
        
        if inspect.iscoroutinefunction(args[0]):
            asyncio.run(self._bsclient.start(main=args[0](),host=self._serveHost,port=self._servePort))
  
        elif inspect.isfunction(args[0]) or inspect.ismethod(args[0]):
            self.__enter__()
            try:
                args[0]()
            finally:
                while True:
                    if not self._bsclient._isRuning:
                        break
                    if not self._bsclient.hasSubscribe(returnTopics=False):
                        _ = asyncio.run_coroutine_threadsafe(self._bsclient.exit(),self._enterLoop)
                        _.result()
                        break
                    time.sleep(1)

                self.__exit__(None,None,None)


    async def start(self,main:Union[Future,Coroutine,Callable]=None,uri:str=None,host:str=None,port:int=None,runforever:bool=False):
        """# 启动连接
        存在订阅的话题时，程序会一直等待话题的推送，无订阅话题时程序在执行完入口函数`main`后自动退出
        Args:            
            main:入口函数，它是一个可等待对象，可以是协程函数、协程对象或Future对象。为指定时默认为
            uri: 服务器地址 例：`utran://127.0.0.1:8081`
            host: 不使用uri时可以直接指定服务器的host和port
            port: 不使用uri时可以直接指定服务器的host和port
            runforever: 是否一直运行,默认入口函数执行完毕且无任何订阅时会自动退出
        """
        host = host or self._serveHost
        port = port or self._servePort
        # 基础客户端
        
        await self._bsclient.start(main=main,uri=uri,host=host,port=port,runforever=runforever)


    def subscribe(self,
                topic:Union[str,tuple[str]],
                callback:callable,
                *,
                timeout:int=None,
                ignore:bool=None)->Union[Coroutine,dict]:
        """# 订阅话题
        支持同步和异步的调用，
        存在订阅的话题时，程序会一直等待话题的推送，无订阅话题时程序在执行完入口函数`main`后自动退出
        
        Args:
            topic: 话题
            callback: 回调函数，有两个参数 msg,topic。支持异步和同步回调函数, 
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
        
        Returns:
            {'allTopics': ['topic1','topic2'], 'subTopics': ['topic2']}
        
        |allTopics|subTopics|
        |---------|-----------|
        |所有已订阅的话题 `list`|本次订阅的话题 `list`|
        """
        coro = self._bsclient.subscribe(topic=topic,callback=callback,timeout=timeout,ignore=ignore)
        if self._enterLoop:
            futrue = asyncio.run_coroutine_threadsafe(coro,self._enterLoop)
            return futrue.result()

        else:
            return coro
    

    def unsubscribe(self,
                    *topic:str,
                    timeout:int=None,
                    ignore:bool=None)->Union[Coroutine,dict]:
        """# 取消订阅话题
        支持同步和异步的调用，
        存在订阅的话题时，程序会一直等待话题的推送，无订阅话题时程序在执行完入口函数`main`后自动退出
        Args:
            topic: 话题
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充

        Returns:
            {'allTopics': ['topic1'], 'unSubTopics': ['topic2']}   

        |allTopics|unSubTopics|
        |---------|-----------|
        |所有已订阅的话题 `list`|本次取消订阅的话题 `list`|
        """
        coro = self._bsclient.unsubscribe(*topic,timeout=timeout,ignore=ignore)
        if self._enterLoop:
            futrue = asyncio.run_coroutine_threadsafe(coro,self._enterLoop)
            return futrue.result()
        else:
            return coro
    


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


    def exit(self):
        """# 退出程序
        支持同步和异步的调用，
        """
        coro = self._bsclient.exit()
        if self._enterLoop:
            futrue = asyncio.run_coroutine_threadsafe(coro,self._enterLoop)
            return futrue.result()
        else:
            return coro
        

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
    

    def __enter__(self):        
        self._enterLoop = asyncio.new_event_loop()
        def worker(loop:asyncio.AbstractEventLoop):
            loop.run_until_complete(self._bsclient.start(runforever=True))

        self._thread = threading.Thread(target=worker, args=(self._enterLoop,))
        self._thread.start()

        while True:
            if self._bsclient._isRuning:
                break
            time.sleep(0.1)
        return self
    

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type:
                raise exc_type(exc_value)
        finally:
            self._thread.join()
            self._enterLoop.close()
            self._enterLoop = None


    