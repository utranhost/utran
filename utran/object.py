from enum import Enum
from dataclasses import dataclass, field
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

@dataclass
class UtBaseRequest:
    """基础请求体"""
    id:int
    
    def to_dict(self):
        d = self.__dict__
        if d.get('requestType'):
            d['requestType'] = d['requestType'].value
        return 

@dataclass
class RpcRequest(UtBaseRequest):
    """Rpc请求体"""
    methodName: str
    args: Union[tuple, list] = field(default_factory=tuple)
    dicts: dict = field(default_factory=lambda: defaultdict(list))
    requestType: UtRequestType = UtRequestType.RPC

@dataclass
class PubRequest(UtBaseRequest):
    """Publish请求体"""
    topic: str
    msg: any
    requestType:UtRequestType= UtRequestType.PUBLISH

@dataclass
class SubRequest(UtBaseRequest):
    """Subscribe请求体"""
    topics:List[str]
    requestType:UtRequestType= UtRequestType.SUBSCRIBE

@dataclass
class UnSubRequest(UtBaseRequest):
    """Unsubscribe请求体"""
    topics:List[str]
    requestType: UtRequestType = UtRequestType.UNSUBSCRIBE


@dataclass
class UtResponse:
    """响应体"""
    id:int                              #本次请求的id
    responseType:UtRequestType
    state:UtState
    methodName: Union[str,None] = None
    result:any = None                   #执行结果
    error:str = ''                      # 失败信息，执行失败时才会有内容
    
    def to_dict(self):
        d = self.__dict__
        d['responseType'] = d['responseType'].value
        d['state'] = d['state'].value
        return d


@dataclass
class BaseDataModel:
    """基础数据模型"""
    pass