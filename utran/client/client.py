import asyncio
from functools import partial
import threading
import time
from typing import Coroutine, Union
from utran.client.baseclient import BaseClient
import inspect
from utran.log import logger

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
        coro:Coroutine = self._accessProxy_._client_._base_call(methodName=self._accessProxy_._temp_name_,args=args,dicts=dicts,**self._accessProxy_._temp_opts_)
        if self._accessProxy_._client_._loop:
            return self._accessProxy_._client_._use_sync(coro)
        else:
            return coro

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

    def __call__(self,*,timeout:int=None,ignore:bool=None,multicall:bool=False):
        """# 设置调用选项
        Args:
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒） ，默认为为client实例化的值
            encrypt: 是否加密， 默认为为client实例化的值
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充，默认为为client实例化的值
            multicall: 是否标记为合并调用
        """
        self._temp_opts_ = dict(timeout= timeout,
                                ignore = self._client_._bsclient._ignore if ignore==None else ignore,
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
    __slots__ = ('_loop','_thread','_bsclient','_is_loop_autogen')
    
    def __init__(self, 
                 url: str = 'ws://localhost:8080', 
                 maxReconnectNum: int = 10, 
                 ignore: bool = True, 
                 compress: int = 0, 
                 max_msg_size: int = 4 * 1024 * 1024, 
                 username: str = None, 
                 password: str = None,
                 loop = None) -> None:
        
        self._bsclient = BaseClient(url, maxReconnectNum, ignore, compress, max_msg_size, username, password)
        self._loop:asyncio.AbstractEventLoop = loop
        self._is_loop_autogen = False


    def __call__(self, *args: any,
                 url:str=None,
                 username:str=None,
                 password:str=None,
                 loop:asyncio.AbstractEventLoop = None) -> callable:
        """指定入口函数，可以使用装饰器方式指定入口函数"""
        if len(args)==0:
            return partial(self.__call__,url=url,username=username,password=password,loop=loop)
        
        main=args[0]        
        loop = loop or self._get_event_loop()
        if inspect.iscoroutinefunction(main):            
            try:
                async def run():                    
                    await self._bsclient.start(url=url,username=username,password=password)
                    if inspect.signature(main).parameters.values():
                        await main(self)
                    else:
                        await main()
                    await self._bsclient.__aexit__()
                loop.run_until_complete(run())
            finally:
                if self._is_loop_autogen:
                    loop.stop()
                    loop.close()
        

        elif inspect.isfunction(main) or inspect.ismethod(main):            
            try:
                self.start(url=url,username=username,password=password,loop=loop)
                if inspect.signature(main).parameters.values():
                    main(self)
                else:
                    main()
            finally:
                self.__exit__()

        return main


    def start(self,url:str=None,username:str=None,password:str=None,loop:asyncio.AbstractEventLoop = None):
        """# 启动连接
        存在订阅的话题时，程序会一直等待话题的推送，无订阅话题时程序在执行完入口函数`main`后自动退出
        Args:            
            main:入口函数，它是一个可等待对象，可以是协程函数、协程对象或Future对象。为指定时默认为
            uri: 服务器地址 例：`utran://127.0.0.1:8081`
            host: 不使用uri时可以直接指定服务器的host和port
            port: 不使用uri时可以直接指定服务器的host和port
            runforever: 是否一直运行,默认入口函数执行完毕且无任何订阅时会自动退出
        """
        self._loop = loop or self._get_event_loop()
        coro = self._bsclient.start(url=url,username=username,password=password)

        if self._loop==None:
            return coro
        
        def worker():
            logger.debug("ws线程运行")
            async def waitExit():
                await self._bsclient._exitEvent.wait()
                
            self._loop.run_until_complete(coro)
            self._loop.run_until_complete(waitExit())
            logger.debug("ws线程退出")

        self._thread = threading.Thread(target=worker)
        self._thread.start()

        
        while True:
            if self._bsclient._isclosed==0: # 等待连接成功
                break
            time.sleep(0.5)


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
        if not self._has_start():
            logger.warning(f'程序已经关闭,无法执行:"subscribe"方法')
            return
        coro = self._bsclient.subscribe(topic=topic,callback=callback,timeout=timeout,ignore=ignore)
        if self._loop:
            return self._use_sync(coro)
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
        if not self._has_start(): 
            logger.warning(f'程序已经关闭,无法执行:"unsubscribe"方法')
            return
        coro = self._bsclient.unsubscribe(*topic,timeout=timeout,ignore=ignore)
        if self._loop:            
            return self._use_sync(coro)
        else:
            return coro
    


    def multicall(self,*calls:Coroutine,ignore:bool=None,retransmitFull:bool=False)->Union[list,Coroutine]:
        """# 合并多次调用远程方法或函数
        支持同步和异步的调用，
                同步调用方式会：1自动建立连接 -- 2任务执行完毕 --3自动关闭连接，适用于未建立连接时使用。
                异步调用方式会：1使用现有的连接-- 2任务执行完毕。适用于已建立连接时。
        Args:
            *calls: 需要远程调用协程对象
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
            retransmitFull: 于服务器失联后，默认只重发未收到响应的请求，如果为True则重发全部请求
        
        Returns:
            执行结果按顺序放在列表中返回
        """
        if not self._has_start():
            logger.warning(f'程序已经关闭,无法执行:"multicall"方法')
            return
        coro = self._bsclient.multicall(*calls,ignore=ignore,retransmitFull=retransmitFull)

        if self._loop:
            # with关键字调用、同步指定入口
            return self._use_sync(coro)
        else:
            # 异步指定入口
            return coro


    def _get_event_loop(self):
        """# 获取可用的事件循环

        Returns:
            1.当前存在没有被关闭的loop，则返回该loop，当程序退出时不会关闭该loop
            2.否者生成新的loop并标记未自动生成的，当退出程序时会自动关闭该loop
        
        """
        if self._loop and not self._loop.is_closed():
            return self._loop
        else:
            self._is_loop_autogen = True
            return asyncio.new_event_loop()


    def _has_start(self):
        """# 是否调用了start
        未运行start时，进行自启动,当执行exit过后，不会自动
        """
        if self._bsclient._isclosed == -1:
            logger.debug('自启动..')
            self.start(loop=self._get_event_loop())            
        elif self._bsclient._isclosed == 1:             
             return False        
        return True

    def _use_sync(self,coro:Coroutine):
        futrue = asyncio.run_coroutine_threadsafe(coro,self._loop)
        return futrue.result()


    def exit(self):
        """# 退出程序
        支持同步和异步的调用，
        """
        if not self._has_start():
            logger.warning(f'程序已经关闭,无法执行:"exit"方法')
            return
        coro = self._bsclient.exit()
        if self._loop:            
            self._use_sync(coro)
            if self._is_loop_autogen:
                self._loop.stop()
                self._loop.close()
                self._loop = None
        else:
            return coro
        
    
    def without_sub_exit(self):
        """无订阅时退出"""
        if not self._has_start():
            logger.warning(f'程序已经关闭,无法执行:"without_sub_exit"方法')
            return
        coro = self._bsclient.__aexit__(None,None,None)
        if self._loop:
            try:
                self._use_sync(coro)
                if self._is_loop_autogen:
                    self._loop.stop()
                    self._loop.close()
                    self._loop = None
            except Exception as e:
                logger.warning(e)
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
        if not self._has_start():
            logger.warning(f'程序已经关闭,无法执行:"call"方法')
            return
        return AccessProxy(self)
    

    @property
    def _base_call(self):
        return self._bsclient.call

    def __enter__(self):
        self._loop = self._get_event_loop()
        self.start()
        return self
    
    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        try:
            if exc_type:
                raise exc_type(exc_value)
            if self._loop:
                self.without_sub_exit()
                return
        except:
            if self._loop:
                self.exit()

    async def __aenter__(self):
        await self._bsclient.__aenter__()
        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._bsclient.__aexit__(exc_type, exc_val, exc_tb)



    