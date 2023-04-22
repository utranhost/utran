from typing import Any, Callable, Coroutine, Union
import aiohttp
import asyncio


def asyncfn_runner(fn:Union[Callable,Coroutine],*args,**kwds):
    """子进程或线程中的异步执行器"""
    if asyncio.iscoroutinefunction(fn):
        return asyncio.run(fn(*args,**kwds))
    elif asyncio.iscoroutine(fn):
        return asyncio.run(fn)



class WsClinet:
    def __init__(self,url:str='ws://localhost:8080',maxReconnectNum:int=10) -> None:
        self._url = url
        self._session = aiohttp.ClientSession()
        self._ws:aiohttp.ClientWebSocketResponse = None
        self._rpc_requests = dict()
        self._isclosed = True
        self._maxReconnectNum = maxReconnectNum
        self._reconnect_attempts = 0

    async def start(self,url:str=None):
        self._url = url or self._url
        await self.connect()
        self._reconnect_attempts = 0
        print("连接成功")
        for v in self._rpc_requests.values():
            futrue:asyncio.Future = v[0]
            futrue.set_exception(Exception('disconnection'))


    async def connect(self):
        self._ws = await self._session.ws_connect(self._url)
        print("start")
        self._receive_task = asyncio.create_task(self.__receive())  
        self._isclosed = False


    async def _reconnecting(self):
        """断线重连"""
        if not self._isclosed:
            print('重连',len(self._rpc_requests.keys()))

            for i in range(self._maxReconnectNum):
                try:
                    print(f'Reconnecting... (attempt {i+1})')
                    await asyncio.sleep(0.5 * (min(i, 10)))
                    await self.start()
                    return
                except Exception as e:
                    print(f'WebSocket connection error: {e}')                    
                    continue

            await self.exit()
            for v in self._rpc_requests.values():
                futrue:asyncio.Future = v[0]
                futrue.set_exception(ConnectionResetError('Max reconnect attempts reached. Aborting.'))

        else:
            await self.exit()


    async def __receive(self):
        print('接收开启')
        while True:            
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = msg.json()

                if data['responseType'] == 'publish':
                    print('publish',data)
                    # channel, message = data['params']
                    # callbacks = self.subscriptions.get(channel, [])

                    # for callback in callbacks:
                    #     asyncio.create_task(callback(channel, message))
                elif data['responseType'] == 'rpc':
                    
                    request_id = data['id']
                    future,request = self._rpc_requests.pop(request_id)
                    future.set_result(data)
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                break

        asyncio.create_task(self._reconnecting())
        print('接收关闭')


    async def _send(self,request:dict,timeout:int=None)->dict:
        await self._ws.send_json(request)
        futrue = asyncio.Future()
        self._rpc_requests[request['id']] = (futrue,request)
        response = await asyncio.wait_for(futrue,timeout)
        return response
    


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
    


    async def call(self,request:dict,timeout:int=None,multicall:bool=False,ignore:bool=True)->Union[Any,dict]:
        """# 调用远程方法或函数
        Args:
            request: 请求体
            timeout: 本地等待响应超时，抛出TimeoutError错误（单位：秒）
            multicall: 是否标记为合并调用
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
        """
        if multicall:
            return request,timeout
        else:
            result = await self._send(request,timeout=timeout)
            if ignore:
                return result.get('result')
            else:
                raise RuntimeError(f"Response '{result.get('responseType')}' Error，"+result.get('error'))


    async def multicall(self,*calls,ignore:bool=True,retransmitFull:bool=False)->list:
        """# 合并多次调用远程方法或函数
        Args:
            *calls: 需要远程调用协程对象
            ignore: 是否忽略远程执行结果的错误，忽略错误则值用None填充
            retransmitFull: 于服务器失联后，默认只重发未收到响应的请求，如果为True则重发全部请求

        Returns:
            执行结果按顺序放在列表中返回
        """
        success = []
        faild_calls = []
        faild_indexs = []
        if asyncio.iscoroutine(calls[0]):            
            requests = [await c for c in calls]
        else:
            requests = calls
        

        res = await asyncio.gather(*[self._send(request,timeout=timeout) for request,timeout in requests],return_exceptions=True)
        for i in range(len(res)):
            result = res[i]
            if isinstance(result, Exception):
                # 处理连接错误
                if str(result)=='disconnection':
                    if retransmitFull:
                        faild_calls = requests
                        success = []
                        break
                    else:
                        faild_calls.append(requests[i])
                        faild_indexs.append(i)
                else:
                    raise result
            else:
                # 处理成功响应
                if result.get('state') or ignore:
                    success.append(result.get('result'))
                else:
                    raise RuntimeError(f"Response '{result.get('responseType')}' Error，"+result.get('error'))
        
        if faild_calls:
            res = await self.multicall(*faild_calls,ignore=ignore,retransmitFull=retransmitFull)
            if retransmitFull:
                return res
            else:
                [success.insert(faild_indexs[i],res[i]) for i in range(len(faild_calls))]
        return success
  

    async def exit(self):
        self._isclosed = True
        await self._ws.close()
        await self._session.close()


async def main():
    client = WsClinet(maxReconnectNum=3)
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
    await client.exit()


asyncio.run(main())
