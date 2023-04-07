

import asyncio
from typing import List, Union
from utran.object import UtRequest, UtResponse
from utran.log import logger

class ResultQueue:
    """服务器响应的结果队列"""
    
    __slots__ = ('_responses','_events','_requests')
    def __init__(self) -> None:
        self._responses = dict()   # {id:res,id2:res}
        self._events = dict()  # {id1:e,id2:e}
        self._requests = dict()
        
    def has_request_cache(self):
        """缓存中是否还有未响应的请求"""
        if self._requests:
            return True
        else:
            return False
    
    def pop_cache_request(self,id:int)->UtRequest:
        """获取缓存中的未响应的指定请求，并清除"""
        return self._requests.pop(id)


    async def wait_response(self,request:UtRequest,timeout)->asyncio.Event:
        """缓存请求，并设置event等待"""
        event = asyncio.Event()
        self._events[request.id] = event
        self._requests[request.id] = request

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.exceptions.TimeoutError:
            raise asyncio.exceptions.TimeoutError(f'Local call timeout ({timeout}s):{request.to_dict()}') 
        response:UtResponse = self._pop_responses(request.id)
        return response

        
    def cache_response(self,response:UtResponse):
        """缓存响应,并放行event等待"""
        self._responses[response.id] = response
        event:asyncio.Event = self._events.pop(response.id) 
        event.set()


    def _pop_responses(self,id:int)->UtResponse:
        """拉取指定id的响应数据，同时清除该id的响应缓存和请求缓存""" 
        self._requests.pop(id)
        return self._responses.pop(id)