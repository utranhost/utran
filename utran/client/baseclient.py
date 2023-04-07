
import asyncio
from asyncio import Future
from functools import partial
import inspect
import time

from typing import Union,Callable,Coroutine
import ujson
from utran.log import logger
from utran.client.que import ResultQueue
from utran.object import UtRequest, UtResponse, UtState, UtType, create_UtRequest,HeartBeat
from utran.utils import parse_utran_uri, unpack_data2_utran


class HeartBeatTimer:
    """# 心跳类
    
    Args:
        ping_sender: 向服务器发ping的执行函数，可以是同步或异步函数
        timeout_callback: 服务器响应超时的回调函数，可以是同步或异步函数
        ping_freq: 发ping的频率(单位：秒)
        pong_timeout: 服务器超时设置，服务器超过设定值没有回应时执行timeout_callback
    """
    __slots__=('_ping_freq','_pong_timeout','_pingTask','_timeoutTask','_ping_sender','_timeout_callback','_loop','_lastsendTime')

    def __init__(self,
                 ping_sender:Callable,
                 timeout_callback:Callable,
                 ping_freq:int=2,
                 pong_timeout:int=2,
                 ) -> None:
        self._loop = asyncio.get_event_loop()
        self._ping_freq = ping_freq
        self._pong_timeout = pong_timeout
        self._pingTask:asyncio.TimerHandle = None
        self._timeoutTask:asyncio.TimerHandle = None
        self._ping_sender =ping_sender
        self._timeout_callback = timeout_callback

        self._lastsendTime:float = self._loop.time()
        self.alive()

        
    def alive(self):
        """# 服务器确认存活

        步骤:
            > 1.撤销超时任务
            > 2.撤销上次的执行的发ping操作
            > 2.创建新的延迟发ping操作
        """

        if self._timeoutTask:
            self._timeoutTask.cancel()

        if self._pingTask:
            self._pingTask.cancel()

        self._pingTask = self._loop.call_later(self._ping_freq,self.__ping)

    def getResponseDelay(self)->float:
        """# 获取响应延迟时间，
        需要在收到服务器Pong响应时调用

        Returns:
            返回毫秒数，保留小数点后三位        
        """
        t = (time.time() - self._lastsendTime)*1000
        return round(t,3)

    def __timeout(self):
        if inspect.iscoroutinefunction(self._timeout_callback):
            asyncio.create_task(self._timeout_callback())
        else:
            self._timeout_callback()

    def __ping(self):
        if inspect.iscoroutinefunction(self._ping_sender):
            asyncio.create_task(self._ping_sender())
        else:
            self._ping_sender()
        self._lastsendTime:float = time.time()
        self._timeoutTask = self._loop.call_later(self._pong_timeout, self.__timeout)



class BaseClient:
    """# 基础客户端
    Args:
        heartbeatFreq: 心跳频率
        serverTimeout: 服务器心跳响应超时时间，用于判断是否断线，超过此值会进行重连 (单位:秒)
        localTimeout: 本地调用超时 (单位:秒)
        reconnectNum: 断线重连的次数
        ignore: 是否忽略远程调用异常
        encrypt: 是否加密传输
        reslutqueue: 结果队列类
    """
    __slots__=('_reader',
               '_writer',
               '_reslutqueue',
               '_encrypt',
               '_buffer',
               '_lock',
               '_topics_handler',
               '_exitEvent',
               '_heartbeatFreq',
               '_serverTimeout',
               '_localTimeout',
               '_heartbeatTimer',
               '_receive_task',
               '_reconnectTask',
               '_reconnectNum',
               '_serveHost',
               '_servePort',
               '_reconnectingEvent',
               '_lastReconectTime',
               '_main_task',
               '_main',
               '_ignore',
               '_isRuning',
               '_curSendTask')
    
    def __init__(self,
                 *,
                 host:str=None,
                 port:int=None,
                 heartbeatFreq:int=2,
                 serverTimeout:int=2,
                 localTimeout:int=10,
                 reconnectNum:int=32,
                 ignore:bool = False,
                 encrypt: bool = False,
                 reslutqueue:ResultQueue=None) -> None:
        self._reader = None
        self._writer = None
        self._reslutqueue:ResultQueue = reslutqueue or ResultQueue()
        self._encrypt:bool = encrypt                                    # 是否加密
        self._buffer = b''                                              # buffer
        self._lock = asyncio.Lock()                                     # 异步协程锁
        self._topics_handler = dict()                                   # 存放话题和回调函数
        self._exitEvent = asyncio.Event()                               # 用于等待退出
        self._heartbeatFreq:int = heartbeatFreq                         # 心跳频率（单位：秒）
        self._serverTimeout:int = serverTimeout                         # 服务器响应超时时间 （单位：秒）
        self._localTimeout:int = localTimeout                           # 本地调用超时
        self._heartbeatTimer:HeartBeatTimer = None                      # 心跳类
        self._receive_task:asyncio.Task = None                          # 接收服务器消息的任务
        self._reconnectTask:asyncio.Task = None                         # 断线重连任务
        self._reconnectNum:int = reconnectNum                           # 断线重连的次数
        self._serveHost:str = host                                      # 服务器host 
        self._servePort:int = port                                      # 服务器端口号
        self._reconnectingEvent:asyncio.Event = asyncio.Event()         # 用于等待重连
        self._reconnectingEvent.set()               # 默认关闭等待
        self._lastReconectTime:float = None                             # 最后一次重连时间
        self._main_task:asyncio.Task = None
        self._main:callable = None
        self._ignore = ignore                                           # 是否忽略远程调用异常
        self._isRuning = False                                          # 是否运行中
        self._curSendTask:asyncio.Task = None

    async def start(self,main:Union[Future,Coroutine]=None,uri:str=None,host:str=None,port:int=None):
        """# 启动连接
        存在订阅的话题时，程序会一直等待话题的推送，无订阅话题时程序在执行完入口函数`main`后自动退出
        Args:
            uri: 服务器地址
            main:入口函数，这是一个协程对象或Future对象
        """
        main = main or self._main
        assert main,ValueError('No entry function or method was specified')
        self._serveHost = host or self._serveHost
        self._servePort = port or self._servePort
        if uri:
            self._serveHost,self._servePort = parse_utran_uri(uri)
        
        assert self._serveHost and self._servePort,ValueError('Specify the correct host and port.')

        self._reader, self._writer = await asyncio.open_connection(self._serveHost, self._servePort)
        self._receive_task = asyncio.create_task(self.__receive())  
        self._heartbeatTimer = self._heartbeatTimer or HeartBeatTimer(self._ping,self._ping_timeout,self._heartbeatFreq,self._serverTimeout)
        
        self._isRuning = True
        if asyncio.iscoroutine(main):
            result = await main            
            self._receive_task.cancel()
            self._isRuning = False
            await self._close()            
            return result

        if asyncio.iscoroutinefunction(main):
            self._main_task = asyncio.create_task(main())

        try:
            await self._main_task
            if self._topics_handler: logger.info('主函数执行完毕,持续等待订阅推送..')
            self._heartbeatTimer.alive()
        except Exception as e:
            self._exitEvent.set()
            raise e

        if not self._topics_handler:
            self._exitEvent.set()

        await self._exitEvent.wait()
        self._receive_task.cancel()
        self._isRuning = False
        await self._close()
        

    def __call__(self, *args: any, **opts: any) -> callable:
        """# 指定入口函数，可以使用装饰器方式指定入口函数
        opts 选项参数暂时未设置功能，待开发..
        """
        if len(args)==0:
            return partial(self.__call__,**opts)
        if inspect.iscoroutinefunction(args[0]):
            self._main = args[0]
            return args[0]
        raise ValueError('Must be a coroutine function!')
    

    async def _ping(self):
        """向服务器发送ping"""
        try:
            await self._send(None,heartbeat=True)
        except ConnectionResetError as e:
            logger.error('发送PING时服务器错误，'+str(e))



    async def _ping_timeout(self):
        """服务器响应超时，该方法会被执行"""
        logger.error("服务器响应超时，启动断线重连..")
        self._reconnectTask = asyncio.create_task(self._reconnecting())


    async def _reconnecting(self):
        """断线重连"""
        n = self._reconnectNum
        logger.error(f"开始尝试重连,将在{self._reconnectNum}次后停止...")
        self._reconnectingEvent.clear()
        while n>0:
            if n<=12:logger.error(f"剩余{n}次重连..")
            await self._close()
            try:
                self._receive_task.cancel()
                self._reader, self._writer = await asyncio.open_connection(self._serveHost, self._servePort)
                logger.success(f"重连成功")
                self._lastReconectTime = time.time()
                if self._curSendTask and not self._curSendTask.done():
                    self._curSendTask.cancel()
                    self._curSendTask = None

                self._reconnectingEvent.set()
                self._receive_task = asyncio.create_task(self.__receive())

                await asyncio.sleep(0.3)
                self._heartbeatTimer.alive()
                if self._topics_handler:
                    topics = list(self._topics_handler.keys())
                    request:UtRequest = create_UtRequest(dict(requestType=UtType.SUBSCRIBE.value,topics=topics))               
                    await self._send(request,timeout=10,ignore=True)
                    logger.success(f"已重新订阅话题: {topics}.")
                    

                # await self._ping()
                return True

            except Exception as e:
                logger.error(f"重连失败:{e}")
                await asyncio.sleep(1)
            n-=1

        self._receive_task.cancel()    
        self._main_task.cancel()
        logger.error("服务器无响应重连结束，程序退出！")      
        await self.exit()



    async def subscribe(self,
                        topic:Union[str,tuple[str]],
                        callback:callable,
                        *,
                        timeout:int=None,
                        ignore:bool=None)->dict:
        """# 订阅话题
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

        return await self._send(request,timeout=timeout,ignore=ignore)
        

    async def unsubscribe(self,
                          *topic:str,
                          timeout:int=None,
                          ignore:bool=None)->dict:
        """# 取消订阅话题
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
        [self._topics_handler.pop(t) for t in topic if t in self._topics_handler]              


        msg = dict(requestType=UtType.UNSUBSCRIBE.value,topics=topic)
        request:UtRequest = create_UtRequest(msg)
        res = await self._send(request,timeout=timeout,ignore=ignore)
        if not self._topics_handler:logger.warning('已无任何订阅.')
        return res
        

    async def call(self,
                   methodName:str,
                   args:list=tuple(),
                   dicts:dict=dict(),
                   *,
                   timeout:int=None,
                   multicall:bool=False,
                   encrypt:bool=None,
                   ignore:bool=None)->Union[UtResponse,dict]:
        """# 调用远程方法或函数
        Args:
            methodName: 远程的方法或函数的名称
            args: 列表参数
            dicts: 字典参数
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            multicall: 是否标记为合并调用
            encrypt: 是否加密
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
        """
        msg = dict(requestType=UtType.RPC.value,methodName=methodName,args=args,dicts=dicts)
        if multicall:
            return msg
        else:
            encrypt = self._encrypt if encrypt==None else encrypt
            request:UtRequest = create_UtRequest(msg,encrypt=encrypt)
            return await self._send(request,timeout=timeout,ignore=ignore)
        

    async def multicall(self,*calls:Coroutine,encrypt:bool = False,timeout:int=None,ignore:bool=None)->list:
        """# 合并多次调用远程方法或函数
        Args:
            *calls: 需要远程调用协程对象
            encrypt: 是否加密
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
        
        Returns:
            执行结果按顺序放在列表中返回
        """
        msgs = await asyncio.gather(*calls)
        encrypt = self._encrypt if encrypt==None else encrypt
        request:UtRequest = create_UtRequest(dict(requestType=UtType.MULTICALL,multiple=msgs),encrypt=encrypt)
        res = await self._send(request,timeout=timeout)

        ignore = self._ignore if ignore== None else ignore
        if ignore:
            return [r.get('result') for r in res]
        else:
            result = []
            for r in res:
                if r.get('state')==UtState.SUCCESS.value:
                    result.append(r.get('result'))
                else:
                    raise RuntimeError(r.get('error'))
            return result
            


    async def _send(self,request:UtRequest,*,timeout:int=None,ignore:bool=None,heartbeat:bool=False):
        timeout = self._localTimeout if timeout==None else timeout
        ignore = self._ignore if ignore== None else ignore            
        # if heartbeat :print("执行发送心跳任务")
        # else: print("执行发送请求任务",request.id)
        try:
            async with self._lock:     # 每次只允许一个协程调用call方法
                if heartbeat:
                    self._writer.write(HeartBeat.PING.value)
                    await self._writer.drain()
                    print("PING")
                    return

                self._writer.write(request.pick_utran_request())
                await self._writer.drain()

                self._curSendTask = asyncio.ensure_future(self._reslutqueue.wait_response(request,timeout=timeout))
                try:
                    response:UtResponse = await self._curSendTask
                except asyncio.exceptions.CancelledError:
                    raise asyncio.exceptions.TimeoutError('服务器断线，尝试重新执行请求')
                
                if response.state == UtState.FAILED:
                    if ignore:return response.result
                    else:
                        raise asyncio.exceptions.TimeoutError(response.error)
                else:
                    return response.result
                
        except asyncio.exceptions.TimeoutError as e:
            await self._reconnectingEvent.wait()
            if self._lastReconectTime is not None:
                # 刚断线重连成功
                async with self._lock:
                    self._reslutqueue.pop_cache_request(request.id)
                    if not self._reslutqueue.has_request_cache():   # 如果没有其他被中断的请求，清除本次断线记录
                        self._lastReconectTime = None
                logger.success(f"接续被中断的请求: ID:{request.id}, {request.requestType.value}.")
                return await self._send(request=request,timeout=timeout,ignore=ignore)
            else:
                # 本地等待超时，非断线原因
                logger.warning(f'Local call timeout ({timeout}s):{request.to_dict()}')
                await self.exit()
                raise e
                

    async def __receive(self):
        print("启动接收任务")
        while True:
            chunk = await self._reader.read(1024)
            if not chunk:
                raise ConnectionError('Connection closed by server')
            
            self._heartbeatTimer.alive()
            # 心跳检测                      
            if chunk == HeartBeat.PONG.value:
                print(f"-PONG: {self._heartbeatTimer.getResponseDelay()}ms")
                continue

            name,message,self._buffer = unpack_data2_utran(chunk, self._buffer)
            if message is not None:
                try:
                    # name:str = name.decode('utf-8')
                    response:UtResponse = UtResponse(**ujson.loads(message.decode('utf-8').strip()))
                except Exception as e:
                    logger.warning(f'服务器消息异常: {e}')
                    continue

                if response.responseType == UtType.PUBLISH:
                    asyncio.create_task(self._handler_publish(**response.result))
                else:
                    self._reslutqueue.cache_response(response)
   

    async def _handler_publish(self,topic:str,msg:any):
        """处理话题推流"""
        callback =  self._topics_handler.get(topic)
        if not callable:            
            # print(f"推送【{topic}】话题:",msg)
            return
        if inspect.iscoroutinefunction(callback):
            await callback(msg,topic)                
        else:
            callback(msg,topic)


    async def _close(self):
        """# 关闭连接"""
        if self._writer is not None:
            try:            
                self._writer.write(b'')
                await self._writer.drain()
            except ConnectionResetError as e:
                pass
            self._writer.close()

        self._reader = None
        self._writer = None

    async def exit(self):
        """# 退出程序
        调用退出时，并不会立即退出，需要等run方法中指定的`main`入口函数执行完毕才会退出。
        """
        self._topics_handler = None
        self._exitEvent.set()

