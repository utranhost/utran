

import asyncio
from utran.object import UtResponse


class ResultQueue:
    """服务器响应的结果队列"""
    
    __slots__ = ('_resluts','_events')
    def __init__(self) -> None:
        self._resluts = dict()   # {id:res,id2:res}
        self._events = dict()  # {id1:e,id2:e}
    
    def push_event(self,id:int,event:asyncio.Event):
        """推入事件"""
        self._events[id] = event
        

    def pull_event(self,id:int):
        """拉取事件，并删除""" 
        if id in self._resluts:
            return self._events.pop(id)
        else:
            # asyncio.sleep(0)
            return

    def push(self,response:UtResponse):
        """推入数据"""
        if response.id:
            self._resluts[response.id] = response
            return True
        else:
            return False
        
    def pull(self,id:int):
        """拉取数据，并删除""" 
        if id in self._resluts:
            return self._resluts.pop(id)
        else:
            # asyncio.sleep(0)
            return