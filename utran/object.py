from enum import Enum
from dataclasses import field
from collections import defaultdict
from typing import List, Union
import uuid
from aiohttp.web_ws import WebSocketResponse
from asyncio import StreamWriter
import asyncio
from typing import List, Union
import ujson

from utran.utils import pack_data2_utran


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
    MULTICALL: str = 'multicall'

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
        
        elif uttype == UtType.MULTICALL.value:
            return UtType.MULTICALL
        
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


class UtRequest:
    """
    
    ## Rpc请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        methodName (str): 调用的方法或函数名
        args (str): 列表参数
        dicts (dict): 字典参数

    ## Subscribe请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        topics (Tuple[str]): 可以同时订阅一个或多个话题

    ## Unsubscribe请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        topics (Tuple[str]): 可以同时取消订阅一个或多个话题

    ## Publish请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        topics (Tuple[str]): 话题
        msg (any): 话题消息

    ## multiple请求体
    Attributes:
        id (int): 请求体id
        requestType (str): 标记请求类型
        multiple (List[dict]): 多次的请求体,其中dict是对应类型的请求体的字典
    """

    __slots__ = ('id', 'requestType', 'methodName', 'args', 'dicts','topics','msg','multiple','encrypt')
    def __init__(self,
                 id:int,
                 requestType: Union[UtType,str],
                 *,
                 methodName:str = None,
                 args: Union[tuple, list] = field(default_factory=tuple),
                 dicts: dict = field(default_factory=lambda: defaultdict(list)),
                 topics: tuple[str] = tuple(),
                 msg:any = None,
                 multiple:list[dict] = [],
                 encrypt:bool = False,
                 ) -> None:
        
        self.id = id
        self.requestType = convert2_UtType(requestType)
        self.methodName = methodName
        self.args = args
        self.dicts = dicts
        self.topics = tuple(topics) if type(topics) == list or type(topics) == tuple else (topics,)
        self.msg = msg
        self.encrypt = encrypt
        self.multiple = multiple

    def to_dict(self):
        """转为字典"""
        if self.requestType == UtType.RPC:
            return dict(id=self.id,
                        requestType=self.requestType.value,
                        methodName=self.methodName,
                        args=self.args,
                        dicts=self.dicts)

        elif self.requestType == UtType.SUBSCRIBE:
            return dict(id=self.id,
                        requestType=self.requestType.value,
                        topics=self.topics)
        
        elif self.requestType == UtType.UNSUBSCRIBE:
            return dict(id=self.id,
                        requestType=self.requestType.value,
                        topics=self.topics)
        
        elif self.requestType == UtType.PUBLISH:
            return dict(id=self.id,
                        requestType=self.requestType.value,
                        topics=self.topics,
                        msg=self.msg)

        elif self.requestType == UtType.MULTICALL:
            return dict(id=self.id,
                        requestType=self.requestType.value,
                        multiple=self.multiple)


    def pick_utran_request(self):
        """生成符合utran协议的请求数据"""
        return pack_data2_utran(self.requestType.value,self.to_dict(),self.encrypt)



REQUEST_ID:int=0
def gen_requestId()->int:
    """生成请求id"""
    global REQUEST_ID
    REQUEST_ID+=1
    return REQUEST_ID


def create_UtRequest(msg:Union[dict,list[dict]],id=None,encrypt=False)->UtRequest:
    """生成UtRequest实例"""
    def gen_request_dict(msg:Union[dict,list[dict]],id=None)->dict:
        id = id or gen_requestId()
        if type(msg)==list:
            multiple = [gen_request_dict(m,id=id) for m in msg]
            msg = dict(id=id,requestType=UtType.MULTICALL.value,multiple=multiple)        
        elif type(msg)==dict:
            msg['id'] = id
            return msg
        else:
            raise ValueError('"msg" must be a dictionary type!')
        return msg
    res:dict = gen_request_dict(msg,id)
    res['encrypt'] = encrypt
    return UtRequest(**res)



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
                 responseType: Union[UtType,str],
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
        if self.responseType == UtType.RPC:
            if self.state == UtState.SUCCESS:
                return dict(
                    id=self.id,
                    responseType=self.responseType.value,
                    state=self.state.value,
                    methodName=self.methodName,
                    result=self.result)
            else:
                return dict(
                    id=self.id,
                    responseType=self.responseType.value,
                    state=self.state.value,
                    methodName=self.methodName,
                    result=self.result,
                    error=self.error)
        else:
            if self.state == UtState.SUCCESS:
                return dict(
                    id=self.id,
                    responseType=self.responseType.value,
                    state=self.state.value,
                    result=self.result)
            else:
                return dict(
                    id=self.id,
                    responseType=self.responseType.value,
                    state=self.state.value,
                    result=self.result,
                    error=self.error)

    
    
class ClientConnection:
    """客户端连接"""
    __slots__=('topics','sender','__id','_encrypt','_single_semaphore')
    def __init__(self,sender:Union[StreamWriter,WebSocketResponse],encrypt:bool=False):
        self.topics = []
        self.__id = str(uuid.uuid4())
        self.sender = sender
        self._encrypt=encrypt
        self._single_semaphore = asyncio.Semaphore(1)
        
    @property
    def id(self):
        return self.__id

    async def send(self,response:UtResponse):
        async with self._single_semaphore:     # 每次只允许一个协程调用send方法     
            if isinstance(self.sender,StreamWriter):
                msg = pack_data2_utran(response.responseType.value,response.to_dict(),self._encrypt)
                await self.__send_by_sw(msg)
            elif isinstance(self.sender,WebSocketResponse):
                await self.__send_by_ws(response.to_dict())
            else:
                raise RuntimeError('Invalid sender, it must be an instance of StreamWriter or WebSocketResponse')
    
    async def __send_by_sw(self,msg:bytes):        
        w:StreamWriter = self.sender
        w.write(msg)
        await w.drain()

    async def __send_by_ws(self,msg:dict):
        w:WebSocketResponse = self.sender
        await w.send_str(ujson.dumps(msg))


    def add_topic(self,topic:str)->Union[str,None]:
        """# 添加指定的topic
        Returns:
            返回添加成功的topic
        """
        if topic not in self.topics:
            self.topics.append(topic)
            return topic
 
    def remove_topic(self,topic:str)->Union[str,None]:
        """# 移除指定的topic
        Returns:
            返回移除成功的topic
        """
        if topic in self.topics:
            self.topics.remove(topic)
            return  topic


class SubscriptionContainer:
    """
    # 存放订阅者和订阅话题的容器
        
    """
    __slots__=('__subscribes','__topics') 

    def __init__(self) -> None:
        self.__subscribes = dict()   # {客户端id1:{writer:writer,topics:[话题1,话题2,...]},客户端id2:{writer:writer,topics:[话题1,...]}}
        self.__topics = dict()       # {话题1:[客户端id1,客户端id2,..],话题2:[客户端id1,..]}     

    def has_sub(self,subId:str):
        """指定id 查询订阅者是否存在"""
        if subId in self.__subscribes:
            return True
        return False

    def add_sub(self,cc:ClientConnection,topics:Union[str,list]=None)->Union[List[str],None]:
        """# 添加订阅者
        Returns:
            返回本次成功订阅的topic   
        """
        if cc.id not in self.__subscribes:
            self.__subscribes[cc.id] = cc
        if topics != None:
            return self.add_topic(cc.id,topics)

    def add_sub_by_id(self,subId:str,sender:Union[StreamWriter,WebSocketResponse],topic:Union[str,list]=None):
        """通过id添加订阅者"""
        if subId not in self.__subscribes:
            self.__subscribes[subId]= ClientConnection(subId,sender)
        if topic != None:
            self.add_topic(subId,topic)

    def del_sub(self,subId:str):
        """删除订阅者,成功返回订阅者，否则返回None"""
        s:ClientConnection = self.__subscribes.get(subId)
        if s:
            if len(s.topics)>0:
                for topic in s.topics:
                    if self.__topics.get(topic) and subId in self.__topics[topic]:
                        self.__topics[topic].remove(subId)
            return self.__subscribes.pop(subId)

    def add_topic(self,subId:str,topic:Union[str,list])->list:
        """# 为订阅者，增加订阅话题
        注: topic 会被转为纯小写
        Returns:
            返回本次成功订阅的topic        
        """
        ok = []
        if type(topic) is list:
            for t in topic:
                t_ = self.add_topic(subId,t)
                if t_: ok.append(t_)
        else:
            topic = topic.lower().strip()
            if not topic: return
            s:ClientConnection = self.__subscribes.get(subId)
            if s:                
                if topic not in self.__topics:
                    self.__topics[topic] = []
                if subId not in self.__topics[topic]:
                    self.__topics[topic].append(subId)
                return s.add_topic(topic)
            else:
                raise ValueError('订阅者不存在')
        return ok

    def remove_topic(self,subId:str,topic:Union[str,list])->List[str]:
        """# 为订阅者，删除某些订阅话题
        Returns:
            返回本次移除成功的topic
        """
        ok = []
        if type(topic) is list:
            for t in topic:
                t_ = self.remove_topic(subId,t)
                if t_: 
                    ok.append(t_)
        else:  
            topic = topic.lower().strip()
            if not topic: return
            s:ClientConnection = self.__subscribes.get(subId)
            if s:
                subIds:list = self.__topics.get(topic) or []
                if s.id in subIds:
                    self.__topics[topic].remove(s.id)
                return s.remove_topic(topic)
            else:
                raise ValueError('订阅者不存在')
        return ok


    def get_sub_by_id(self,subId:str)->ClientConnection:
        """通过id获取订阅者的客户端连接实例"""
        return self.__subscribes.get(subId)

    def get_subId_by_topic(self,topic:str)->list:
        """获取指定话题下所有的订阅者的id"""
        all_subId:list = self.__topics.get(topic.lower().strip())
        all_subId = all_subId or []
        return all_subId


class BaseDataModel:
    """基础数据模型"""
    pass
