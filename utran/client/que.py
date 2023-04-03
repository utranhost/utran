

import asyncio
from utran.object import UtRequest, UtResponse


class ResultQueue:
    """服务器响应的结果队列"""
    
    __slots__ = ('_responses','_events','_requests')
    def __init__(self) -> None:
        self._responses = dict()   # {id:res,id2:res}
        self._events = dict()  # {id1:e,id2:e}
        self._requests = dict()
        

    async def wait_response(self,request:UtRequest,timeout)->asyncio.Event:
        """缓存请求，并设置event等待"""
        event = asyncio.Event()
        self._events[request.id] = event
        self._requests[request.id] = request

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError('Request timed out') 
        response:UtResponse = self.pop_responses(request.id)
        return response

        
    def cache_response(self,response:UtResponse):
        """缓存响应,并放行event等待"""
        self._responses[response.id] = response
        event:asyncio.Event = self._events.pop(response.id) 
        event.set()


    def pop_responses(self,id:int)->UtResponse:
        """拉取指定id的响应数据，同时清除该id的响应缓存和请求缓存""" 
        self._requests.pop(id)
        return self._responses.pop(id)