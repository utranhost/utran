from enum import Enum
from dataclasses import field
from collections import defaultdict
from typing import List, Union


class HeartBeat(Enum):
    """心跳"""
    PING:bytes= b'PING'
    PONG:bytes= b'PONG'

class UtRequestType(Enum):
    """请求类型"""
    GET:str = 'get'
    RPC:str = 'rpc'
    POST:str = 'post'
    SUBSCRIBE:str = 'subscribe'
    UNSUBSCRIBE:str = 'unsubscribe'
    PUBLISH:str = 'publish'

class UtState(Enum):
    """状态"""
    FAILED:str = 'failed'
    SUCCESS:str = 'success'

class UtBaseRequest:
    """基础请求体"""
    __slots__ = ('id','requestType')

    def __init__(self,id:int,requestType:UtRequestType) -> None:
        self.id = id
        self.requestType:UtRequestType = requestType


class RpcRequest(UtBaseRequest):
    """Rpc请求体"""
    __slots__ = ('methodName','args','dicts')

    def __init__(self,
                 id:int,
                 methodName: str,
                 args: Union[tuple, list]=field(default_factory=tuple),
                 dicts: dict=field(default_factory=lambda: defaultdict(list))) -> None:
        super().__init__(id, UtRequestType.RPC)

        self.methodName= methodName
        self.args = args
        self.dicts = dicts
        

class PubRequest(UtBaseRequest):
    """Publish请求体"""

    __slots__ = ('topic','msg')
    def __init__(self, id: int, topic: str,msg: any) -> None:
        super().__init__(id, UtRequestType.PUBLISH) 
        self.topic = topic
        self.msg = msg

class SubRequest(UtBaseRequest):
    """Subscribe请求体"""
    
    __slots__ = ('topics',)
    def __init__(self, id: int, topics:List[str]) -> None:
        super().__init__(id, UtRequestType.SUBSCRIBE) 
        self.topics = topics

class UnSubRequest(UtBaseRequest):
    """Unsubscribe请求体"""

    __slots__ = ('topics',)
    def __init__(self, id: int, topics:List[str]) -> None:
        super().__init__(id, UtRequestType.UNSUBSCRIBE) 
        self.topics = topics



class UtResponse:
    """响应体"""

    __slots__ = ('id','responseType','state','methodName','result','error')
    def __init__(self,
                 id:int,
                 responseType:UtRequestType,
                 state:UtState,
                 methodName: Union[str,None] = None,
                 result:any = None,
                 error:str = '') -> None:
        self.id = id
        self.responseType = responseType
        self.state = state
        self.methodName = methodName
        self.result = result
        self.error = error

    def to_dict(self):
        return dict(
            id=self.id,
            responseType = self.responseType.value,
            state = self.state.value,
            methodName = self.methodName,
            result = self.result,
            error = self.error)


class BaseDataModel:
    """基础数据模型"""
    pass