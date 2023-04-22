from typing import Any,Union
import aiohttp
import asyncio

from utran.object import UtType, gen_requestId
from utran.log import logger



class BaseClient:
    """
    Args:
        url: 服务器地址
        maxReconnectNum: 断线后最大重连次数
        ignore: 全局设置，是否忽略远程执行结果的错误，忽略错误则值用None填充
        compress: 是否压缩数据
        max_msg_size: 表示接收消息的最大大小（以字节为单位）。如果接收到的消息大小超过该值，则会引发异常。
    """
    __slots__ = ('_url','_session','_ws','_rpc_requests','_isclosed','_maxReconnectNum','_reconnect_attempts','_topics_handler','_ignore',
                 '_exitEvent','_compress','_max_msg_size','_receive_task','__auth','_hasReconected')
    def __init__(self,
                 url:str='ws://localhost:8080',
                 maxReconnectNum:int=10,
                 ignore:bool=True,
                 compress: int = 0,
                 max_msg_size: int = 4 * 1024 * 1024,
                 username:str=None,
                 password:str=None) -> None:
        self._url = url
        self._session:aiohttp.ClientSession = None
        self._ws:aiohttp.ClientWebSocketResponse = None
        self._rpc_requests = dict()
        self._isclosed:int = -1       # -1表示还未初始化，0表示已连接，1表示断开连接
        self._maxReconnectNum = maxReconnectNum
        self._reconnect_attempts = 0
        self._topics_handler = dict()
        self._ignore = ignore
        self._exitEvent = asyncio.Event()                               # 用于等待退出
        self._compress = compress
        self._max_msg_size = max_msg_size
        self._receive_task = None
        self._hasReconected:bool = False                                # 是否刚刚重连

        if username!=None or password!=None:
            assert username!=None,'username is None.'
            assert password!=None,'password is None.'
            self.__auth:aiohttp.BasicAuth = aiohttp.BasicAuth(username,password)
        else:
            self.__auth:aiohttp.BasicAuth = aiohttp.BasicAuth('utranhost','utranhost')
        

    async def start(self,url:str=None,username:str=None,password:str=None):
        self._url = url or self._url
        self._session = aiohttp.ClientSession() if self._session==None or self._session.closed else self._session
        
        if username!=None or password!=None:
            assert username!=None,'username is None.'
            assert password!=None,'password is None.'
            self.__auth:aiohttp.BasicAuth = aiohttp.BasicAuth(username,password)


        await self.connect()
        self._reconnect_attempts = 0

        
        if self._topics_handler:
            items = self._topics_handler.items()
            topics = [k for k,v in items]
            callbacks = [v for k,v in items]
            await self.subscribe(topics,callbacks,ignore=True)
            logger.success(f"已重新订阅话题: {topics}.")
            self._exitEvent.clear()

        for v in self._rpc_requests.values():
            futrue:asyncio.Future = v[0]
            futrue.set_exception(Exception('disconnection'))

        return self


    async def connect(self):
        self._ws = await self._session.ws_connect(self._url,compress=self._compress,max_msg_size=self._max_msg_size,auth=self.__auth)        
        msg = await self._ws.receive()
        if msg.data != 'ok':
            await self.exit()
            raise ConnectionError(msg.data)
            
        logger.success(f"连接成功.")
        self._receive_task = asyncio.create_task(self.__receive())  
        self._isclosed = 0


    async def _reconnecting(self):
        """断线重连"""
        if self._isclosed==0:
            logger.error(f"断线重连..")
            for i in range(self._maxReconnectNum):
                try:
                    logger.error(f'Reconnecting... (attempt {i+1}/{self._maxReconnectNum})')
                    await asyncio.sleep(0.5 * (min(i, 10)))
                    await self.start()
                    self._hasReconected = True
                    return
                except Exception as e:
                    logger.error(f'WebSocket connection error: {e}')                    
                    continue

            await self.exit()
            for v in self._rpc_requests.values():
                futrue:asyncio.Future = v[0]
                futrue.set_exception(ConnectionResetError('Max reconnect attempts reached. Aborting.'))

        else:
            await self.exit()


    async def __receive(self):
        # print('接收开启')
        while True:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                response:dict = msg.json()
                if response['responseType'] == UtType.PUBLISH.value:
                    asyncio.create_task(self._handler_publish(**response.get('result')))
                elif response['responseType'] in [UtType.RPC.value,UtType.SUBSCRIBE.value,UtType.UNSUBSCRIBE.value]:
                    request_id = response['id']
                    future,request = self._rpc_requests.pop(request_id)
                    future.set_result(response)

            elif msg.type == aiohttp.WSMsgType.CLOSED:
                break
        
        if self._isclosed==0:
            asyncio.create_task(self._reconnecting())
        # print('接收关闭')


    async def _send(self,request:dict,timeout:int=None)->dict:
        try:
            await self._ws.send_json(request)
        except Exception as e:
            # logger.error(e)
            pass
        futrue = asyncio.Future()
        self._rpc_requests[request['id']] = (futrue,request)
        response = await asyncio.wait_for(futrue,timeout)
        return response
    


    async def _handler_publish(self,topic:str,msg:any):
        """处理话题推流"""
        callback =  self._topics_handler.get(topic)
        if not callable:            
            # print(f"推送【{topic}】话题:",msg)
            return
        if asyncio.iscoroutinefunction(callback):
            await callback(msg,topic)                
        else:
            callback(msg,topic)


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
        if type(topic) not in (tuple,list):
            topic = [topic]

        if type(callback) not in (tuple,list):
            callback = [callback]

        if len(topic) != len(callback):
            raise ValueError('The topic must correspond to the callback one by one')

        for t,c in zip(topic,callback):
            if type(t)!=str:                 
                raise ValueError(f'Subscribe Error "{type(t)}" is not a string!')
            if not callable(c):
                raise ValueError(f'Subscribe Error "{type(c)}" is not callable!')
            
            self._topics_handler[t] = c

        request = dict(id=gen_requestId(),requestType=UtType.SUBSCRIBE.value,topics=topic)
        try:
            response:dict = await self._send(request,timeout=timeout)
        except Exception as e:
            if str(e)=='disconnection':
                return await self.subscribe(topic,callback,timeout=timeout,ignore=ignore)
            else:
                raise e
        
        ignore = self._ignore if ignore== None else ignore
        if response.get('state') or ignore:
            self._exitEvent.clear()
            result:dict = response.get('result')    
            logger.success(f'成功订阅:{result.get("subTopics")}')
            return result
        else:
            raise RuntimeError(f"Response '{response.get('responseType')}' Error，"+response.get('error'))


    async def unsubscribe(self,
                          *topic:str,
                          timeout:int=None,
                          ignore:bool=None)->dict:
        """# 取消订阅话题
        存在订阅的话题时，程序会一直等待话题的推送，无订阅话题时程序在执行完入口函数`main`后自动退出
        Args:
            topic: 话题
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）

        Returns:
            {'allTopics': ['topic1'], 'unSubTopics': ['topic2']}   

        |allTopics|unSubTopics|
        |---------|-----------|
        |所有已订阅的话题 `list`|本次取消订阅的话题 `list`|
        """
        if topic:
            [self._topics_handler.pop(t) for t in topic if t in self._topics_handler]              

        request = dict(id=gen_requestId(),requestType=UtType.UNSUBSCRIBE.value,topics=topic)

        try:
            response:dict = await self._send(request,timeout=timeout)        
        except Exception as e:
            if str(e)=='disconnection':
                return await self.unsubscribe(*topic,timeout=timeout,ignore=ignore)
            else:
                raise e
            
        ignore = self._ignore if ignore== None else ignore
        if response.get('state') or ignore:
            result:dict = response.get('result')
            if result!=None:logger.success(f'取消订阅:{result.get("unSubTopics")}')
            if not self._topics_handler:
                logger.debug('已无任何订阅')               
            return result
        else:
            raise RuntimeError(f"Response '{response.get('responseType')}' Error，"+response.get('error'))

    

    async def call(self,
                   methodName:str,
                   args:list=tuple(),
                   dicts:dict=dict(),
                   *,
                   timeout:int=None,
                   multicall:bool=False,
                   ignore:bool=None)->Union[Any,dict]:
        """# 调用远程方法或函数
        Args:
            methodName: 远程的方法或函数的名称
            args: 列表参数
            dicts: 字典参数
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            multicall: 是否标记为合并调用
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
        """
        request = dict(id=gen_requestId(),requestType=UtType.RPC.value,methodName=methodName,args=args,dicts=dicts)
        if multicall:
            return request,timeout
        else:
            try:
                response:dict = await self._send(request,timeout=timeout)
            except Exception as e:
                if str(e)=='disconnection':
                    return await self.call(methodName,args,dicts,timeout=timeout,ignore=ignore)
                else:
                    raise e
                
            ignore = self._ignore if ignore== None else ignore
            if response.get('state') or ignore:
                return response.get('result')
            else:
                raise RuntimeError(f"Response '{response.get('responseType')}' Error，"+response.get('error'))



    async def multicall(self,*calls,ignore:bool=None,retransmitFull:bool=False)->list:
        """# 合并多次调用远程方法或函数
        Args:
            *calls: 需要远程调用协程对象
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
            retransmitFull: 于服务器失联后，默认只重发未收到响应的请求，如果为True则重发全部请求

        Returns:
            执行结果按顺序放在列表中返回
        """
        ignore = self._ignore if ignore== None else ignore
        success = []
        faild_calls = []
        faild_indexs = []
        if asyncio.iscoroutine(calls[0]):            
            requests = [await c for c in calls]
        else:
            requests = calls
        

        res = await asyncio.gather(*[self._send(request,timeout=timeout) for request,timeout in requests],return_exceptions=True)
        for i in range(len(res)):
            response:dict = res[i]
            if isinstance(response, Exception):
                # 处理连接错误
                if str(response)=='disconnection':
                    if retransmitFull:
                        faild_calls = requests
                        success = []
                        break
                    else:
                        faild_calls.append(requests[i])
                        faild_indexs.append(i)
                else:
                    raise response
            else:
                # 处理成功响应
                if response.get('state') or ignore:
                    success.append(response.get('result'))
                else:
                    raise RuntimeError(f"Response '{response.get('responseType')}' Error，"+response.get('error'))
        
        if faild_calls:
            res = await self.multicall(*faild_calls,ignore=ignore,retransmitFull=retransmitFull)
            if retransmitFull:
                return res
            else:
                [success.insert(faild_indexs[i],res[i]) for i in range(len(faild_calls))]
        return success
  

    async def exit(self):        
        self._isclosed = 1
        await self._ws.close()
        await self._session.close()
        self._exitEvent.set()
        self._exitEvent = asyncio.Event()  # 便于下次使用

    async def __aenter__(self):
        await self.start()        
        return self


    async def __aexit__(self, exc_type=None, exc_val=None, exc_tb=None):
        try:
            if exc_type:
                # print(exc_tb)
                raise exc_type(exc_val)
            
            topics = list(self._topics_handler.keys())
            if topics:
                logger.info(f'继续等待订阅推送:{topics}')
                self._exitEvent.clear()
                await self._exitEvent.wait()
                logger.success(f'退出程序')
            else:
                await self.exit()
        except:
            if self._isclosed==0:
                await self.exit()




if __name__ == '__main__':
    async def main():
        client = BaseClient(maxReconnectNum=3)
        await client.start()
        await client._ws.ping(b'ping')
        res = await client.call({'id':1,"requestType":"rpc","methodName":"add0","args":[],"dicts":{"a":1,"b":2}})
        print("ok:",res)
        res= await client.multicall(*[client.call({'id':i,"requestType":"rpc","methodName":"add","args":[],"dicts":{"a":1,"b":i}},multicall=True) for i in range(2,50002)],retransmitFull=False)    
        x = res[0]-1
        for i in res:
            if i == x+1:
                x += 1
            else:
                raise Exception("错误")
            
        print("ok:",res)
        print('总：',len(client._rpc_requests.keys()))
        # await client.exit()


    asyncio.run(main())
