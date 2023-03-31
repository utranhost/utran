from enum import Enum
from dataclasses import field
from collections import defaultdict
from typing import List, Union


class HeartBeat(Enum):
    """心跳"""
    PING: bytes = b'PING'
    PONG: bytes = b'PONG'


class UtType(Enum):
    """请求或响应的类型"""
    GET: str = 'get'
    RPC: str = 'rpc'
    POST: str = 'post'
    SUBSCRIBE: str = 'subscribe'
    UNSUBSCRIBE: str = 'unsubscribe'
    PUBLISH: str = 'publish'


def convert2_UtType(uttype: any) -> UtType:
    if type(uttype) == UtType:
        return uttype
    if type(uttype) == str:
        if uttype == UtType.RPC.value:
            return UtType.RPC

        elif uttype == UtType.SUBSCRIBE.value:
            return UtType.SUBSCRIBE

        elif uttype == UtType.UNSUBSCRIBE.value:
            return UtType.UNSUBSCRIBE

        elif uttype == UtType.PUBLISH.value:
            return UtType.PUBLISH

        elif uttype == UtType.POST.value:
            return UtType.POST

        elif uttype == UtType.GET.value:
            return UtType.GET
    else:
        raise TypeError(f'"{uttype}",Unsupported request type!')


class UtState(Enum):
    """状态"""
    FAILED: int = 0
    SUCCESS: int = 1


def convert2_UtState(state:any)->UtState:
    if type(state) == UtState:
        return state
        
    if state == UtState.FAILED.value:
        return UtState.FAILED
    elif state == UtState.SUCCESS.value:
        return UtState.SUCCESS
    else:
        raise TypeError(f'"{state}",Status value error!')


class UtBaseRequest:
    """基础请求体"""
    __slots__ = ('id', 'requestType')

    def __init__(self, id: int, requestType: UtType) -> None:
        self.id = id
        self.requestType: UtType = requestType


class RpcRequest(UtBaseRequest):
    """# Rpc请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        methodName (str): 调用的方法或函数名
        args (str): 列表参数
        dicts (dict): 字典参数
    """
    __slots__ = ('methodName', 'args', 'dicts')

    def __init__(self,
                 id: int,
                 methodName: str,
                 args: Union[tuple, list] = field(default_factory=tuple),
                 dicts: dict = field(default_factory=lambda: defaultdict(list))) -> None:
        super().__init__(id, UtType.RPC)

        self.methodName = methodName
        self.args = args
        self.dicts = dicts


class PubRequest(UtBaseRequest):
    """# Publish请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        topic (str): 话题
        msg (any): 话题消息
    """

    __slots__ = ('topic', 'msg')

    def __init__(self, id: int, topic: str, msg: any) -> None:
        super().__init__(id, UtType.PUBLISH)
        self.topic = topic
        self.msg = msg


class SubRequest(UtBaseRequest):
    """# Subscribe请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        topics (List[str]): 可以同时订阅一个或多个话题
    """
    __slots__ = ('topics',)

    def __init__(self, id: int, topics: List[str]) -> None:
        super().__init__(id, UtType.SUBSCRIBE)
        self.topics = topics


class UnSubRequest(UtBaseRequest):
    """# Unsubscribe请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        topics (List[str]): 可以同时取消订阅一个或多个话题
    """

    __slots__ = ('topics',)

    def __init__(self, id: int, topics: List[str]) -> None:
        super().__init__(id, UtType.UNSUBSCRIBE)
        self.topics = topics


class UtResponse:
    """# 响应体
    Args:
        id (int): 请求体id
        requestType (str): 标记请求类型
        state (int): 0是失败，1是成功 
        methodName (Union[str,None]): 本次被请求的方法或函数，订阅和取消订阅时此参数为None
        result (any): 执行的结果
        error (str): 存放错误异常信息，默认为''空字符串
    """

    __slots__ = ('id', 'responseType', 'state',
                 'methodName', 'result', 'error')

    def __init__(self,
                 id: int,
                 responseType: UtType,
                 state: UtState,
                 methodName: Union[str, None] = None,
                 result: any = None,
                 error: str = '') -> None:
        self.id = id
        self.responseType = convert2_UtType(responseType)
        self.state = convert2_UtState(state)
        self.methodName = methodName
        self.result = result
        self.error = error

    def to_dict(self):
        """转为字典"""
        return dict(
            id=self.id,
            responseType=self.responseType.value,
            state=self.state.value,
            methodName=self.methodName,
            result=self.result,
            error=self.error)


class BaseDataModel:
    """基础数据模型"""
    pass
