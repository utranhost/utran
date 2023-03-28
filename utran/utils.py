import asyncio
from asyncio import StreamWriter
from collections import defaultdict

from dataclasses import dataclass, field
from functools import partial
import inspect
import ujson
from typing import List, Union


from aiohttp.web_ws import WebSocketResponse
from enum import Enum

class HeartBeat(Enum):
    PING:bytes= b'PING'
    PONG:bytes= b'PONG'

class UtRequestType(Enum):
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


def unpack_data(data:bytes, buffer:bytes=b'',maxsize:int=102400)->tuple[Union[bytes,None],Union[bytes,None],bytes]:
    """
    从接收到的字节流中解析出完整的消息
    :param data: 接收到的字节流
    :param buffer: 缓冲区中未处理完的数据
    :param maxsize: 支持数据的最大长度
    :return: 如果解析成功完整消息，则返回请求类型的名称，消息和剩余字节流；否则返回None和原始字节流
    """
    buffer += data
    
    if len(buffer) < 4:
        return None, None, buffer
    
    # 解析名称
    name_end = buffer.find(b'\n')
    if name_end == -1:
        return None, None, buffer
    
    
    # 解析length
    length_start = name_end + 1
    length_end = buffer.find(b'\n', length_start)
    
    if length_end == -1:
        return None, None, buffer      

    length_str = buffer[length_start:length_end]
    
    if not length_str.startswith(b'length:'):
        raise Exception('Error: Invalid message format. Missing "length" keyword in second line.')
    
    try:
        message_length = int(length_str.split(b':')[1])
    except:
        raise Exception('Error: Value error. "length" value error in second line.')
    
    if message_length > maxsize:
        raise Exception('Message too long')
    
    
    # 解析是否加密
    encrypt_start = length_end + 1
    encrypt_end = buffer.find(b'\n', encrypt_start)
    
    if encrypt_end == -1:
        return None, None, buffer
    
    encrypt_str = buffer[encrypt_start:encrypt_end]
    
    if not encrypt_str.startswith(b'encrypt:'):
        raise Exception('Error: Invalid message format. Missing "encrypt" keyword in third line.')

    try:
        encrypt = int(encrypt_str.split(b':')[1])
    except:
        raise Exception('Error: Value error. "encrypt" value error in third line.')


    # 解析数据内容
    data_start = encrypt_end + 1
    data_end = data_start + message_length
    
    if len(buffer) < data_end:
        return None, None, buffer
    
    name = buffer[:name_end]
    message_data = buffer[data_start:data_end]        
    remaining_data = buffer[data_end:]
    
    if encrypt:
        # 加密算法还未实现
        pass

    return name, message_data, remaining_data
    

def pack_data(res:UtResponse,encrypt=False)->bytes:
    """
    将要发送的消息打包成二进制格式
    :param name: 请求类型的名称
    :param message: 要发送的消息（dict类型）
    :param encrypt: 是否加密数据
    :return: 打包后的二进制数据
    """
    name:str = res.responseType.value
    message:dict = res.to_dict()

    message_json = ujson.dumps(message).encode('utf-8')
    
    if encrypt:
        # 加密算法还未实现
        pass
            
    message_length = len(message_json)
    
    # 打包数据
    data = b''
    data += name.encode('utf-8') + b'\n'
    data += f'length:{message_length}\n'.encode('utf-8')
    data += f'encrypt:{int(encrypt)}\n'.encode('utf-8')
    data += message_json
    
    return data


@dataclass
class BaseDataModel:
    """基础数据模型"""
    pass


def allowType(v,t,n):
    """ 
    # 类型转换
    ### 1.当自身的数据类型与指定的数据一致时，直接返回该数据；
    ### 2.当自身的数据类型与指定的数据不一致，首先尝试是否可以之间转换为该类型，否则，检查是否为允许类型，如果是则转换为该类型的数据，否则报错TypeError。

    Args:
        v: 数据
        t (str): 数据类型
        n (str): 可调用对象的名称
    """
    if type(v)==t:
        return v
    else:
        try:
            v =  t(v)
            return v
        except TypeError:
            pass

        class_ = t
        if class_ and issubclass(class_,BaseDataModel):
            try:
                return class_(**v)
            except Exception as e:
                raise TypeError('Error converting data:',e)
        else:
            raise TypeError(f"Type error, value '{n}' must be {t} type.")


def cheekType(params:tuple,annotations:dict,args:tuple,dicts:dict={})->tuple:
    """
    # 检查类型
    当指定的类型属于BaseDataModel的子类时，将尝试进行自动转换
    """
    args = list(args)   
    
    for i in range(len(params)):
        n = params[i]
        t = annotations.get(n)
        if not t:
            continue
        try:
            v = args[i]
            args[i] = allowType(v,t,n)
        except IndexError:
            try:
                v = dicts[n]
                dicts[n] = allowType(v,t,n)
            except KeyError:
                continue
    return tuple(args),dicts


@dataclass
class RMethod:
    """
    #存放注册方法的数据类
    Attributes:
        name (str): 名称或路径
        methodType (str): 类型 GET / POST / RPC
        callable (callable): 可调用的方法/函数
        checkParams (bool): 是否检查参数
        checkReturn (bool): 是否检查返回值
        cls (str): 类名，类方法才会有
        doc (str): 描述
        params (tuple): 参数
        default_values (tuple): 参数默认值
        annotations (dict): 类型声明
        varargs (str): 参数中*args的名称
        varkw (str): 参数中**dicts的名称
        returnType (str): 返回值的类型
        asyncfunc (bool): 是否为异步函数或方法
    """
    name:str
    methodType:str
    callable:callable
    checkParams:bool
    checkReturn:bool
  
    def __post_init__(self) -> None:
        """"""
        self.cls: str = ''
        if inspect.ismethod(self.callable):
            self.cls = self.callable.__self__.__class__.__name__

        self.params:tuple = tuple(inspect.signature(self.callable).parameters.keys())
        self.default_values:tuple= tuple([i.default for i in tuple(inspect.signature(self.callable).parameters.values()) if i.default is not inspect._empty])
        self.doc:str = inspect.getdoc(self.callable)
        annotations = dict([(k,v.annotation) for k,v in  inspect.signature(self.callable).parameters.items() if v.annotation is not inspect._empty])
        for an in annotations.keys():
            annotations[an] = annotations[an]
        self.annotations:dict = annotations
        sp = inspect.getfullargspec(self.callable)
        self.varargs:str = sp.varargs
        self.varkw:str = sp.varkw
        self.returnType:str = sp.annotations.get('return')
        self.asyncfunc:bool = inspect.iscoroutinefunction(self.callable)


    async def execute(self,args:tuple,dicts:dict)->tuple[UtState,any,str]:
        """ 执行注册的函数或方法
        Returns:
            返回值：状态，结果，错误信息
        """
        result = None
        state = UtState.SUCCESS
        error = ''
        if self.checkParams:
            try:
                args,dicts = cheekType(self.params,self.annotations,args,dicts)
            except Exception as e:
                state = UtState.FAILED
                error = str(e)
                return state,result,error
        try:
            if self.asyncfunc:
                res = await self.callable(*args,**dicts)
            else:
                res = self.callable(*args,**dicts)
            if self.checkReturn and self.returnType:
                try:
                    res= allowType(res,self.returnType,self.name)                    
                    result = res
                except:
                    state = UtState.FAILED
                    error = f"Return value error.'{type(res)}' is not of '{self.returnType}' type"
            else:                
                result = res
        except Exception as e:
            state = UtState.FAILED
            error = str(e)
        
        return state,result,error


class Register:
    """
    注册类，用于注册本地的可调用函数，支持(rpc、get、post)注册
    """
    def __init__(self,checkParams:bool,checkReturn:bool) -> None:
        self.__rpc_methods = dict()     # {method_name:{callable:callable,}}
        self.__get_methods = dict()     # {path:{callable:callable,info:{}}}
        self.__post_methods = dict()    # {path:{callable:callable,info:{}}}
        self.__checkParams = checkParams
        self.__checkReturn = checkReturn

    @property
    def methods_of_get(self):
        return self.__get_methods
    
    @property
    def methods_of_post(self):
        return self.__post_methods

    @property
    def methods_of_rpc(self):
        return self.__rpc_methods
    

    def rpc(self,_f_=None,_n_=None,**opts):
        """# RPC注册
        支持：类/类方法/类实例/函数的注册

        Args:
            第一个参数 (非固定): 1.装饰器用法时，为注册的名称；2.方法调用时，为类/类方法/类实例/函数
            第二个参数 (非固定): 注册的名称，只有在方法调用时才有二个参数
            **opts (可选): 该项只有在给类加装饰器时，用来指定类实例化的参数

        支持装饰器用法 @register.rpc
        """  
        return self._register(_f_,_n_,'rpc',**opts)

    def get(self,_f_=None,_n_=None,**opts):
        """# GET注册

        ## 支持装饰器用法:
        > @register.get("/home")

        ## 无参数使用:
        > @register.get
        > 会将函数名或方法名作为路径使用
        
        """  
        return self._register(_f_,_n_,'get',**opts)

    def post(self,_f_=None,_n_=None,**opts):      
        """# POST注册
        > 使用方法：见GET方法
        """   
        return self._register(_f_,_n_,'post',**opts)


    def _update(self,methodType:str,func:callable,name:str):
        """更新注册表"""
        if methodType=='rpc':
            if not name[0].isalpha():
                raise ValueError(f"'{name}' cannot be used as a func'name,must be startwith a letter")
            self.__rpc_methods[name] = RMethod(name,'RPC',func,self.__checkParams,self.__checkReturn)
            return

        if methodType=='get':
            name = name.replace('.','/')
            if not name.startswith('/'):
                name='/'+name                
            self.__get_methods[name] = RMethod(name,'GET',func,self.__checkParams,self.__checkReturn)
            return

        if methodType=='post':
            name = name.replace('.','/')
            if not name.startswith('/'):
                name='/'+name
            self.__post_methods[name] = RMethod(name,'POST',func,self.__checkParams,self.__checkReturn)
            return


    def _register(self,_f_=None,_n_=None,_t_:str=None,**opts):
        """通用注册，支持注册函数，类（自动实例化），类实例，"""
        if _f_ is None:
            return partial(self._register, _n_=_n_,_t_=_t_,**opts)
        
        if type(_f_)==str:
            _n_ = _f_.strip()
            # if _n_ and _n_[0].isalpha():
            if _n_:
                return partial(self._register,_n_=_n_,_t_=_t_,**opts)
            else:
                raise ValueError(f"'{_f_}' cannot be used as a registered name!")
            
        if inspect.isfunction(_f_) or inspect.ismethod(_f_):
            if not _n_:
                _n_ = _f_.__name__            
            self._update(_t_,_f_,_n_)
        elif inspect.ismodule(_f_):
            raise ValueError(f"'{_f_.__name__} 'module could not be registered!")
        else:            
            if not _n_:
                raise ValueError(f"The name is required!")
            if type(_n_)!=str:
                raise ValueError(f"The name '{_n_}' is not a string!")
            
            if inspect.isclass(_f_):
                _instance = _f_(**opts)
            else:
                _instance = _f_

            for i in dir(_instance):
                if i.startswith("_"):
                    continue
                _f = getattr(_instance,i)
                if inspect.ismethod(_f) or inspect.isfunction(_f):
                    method_name = f'{_n_}.{i}'
                    self._update(_t_,_f,method_name)
        return _f_


class ClientConnection:

    def __init__(self,id:str,sender:Union[StreamWriter,WebSocketResponse],encrypt:bool=False):
        self.topics = []
        self.id = id
        self.sender = sender
        self._encrypt=encrypt

    async def send(self,response:UtResponse):
        if isinstance(self.sender,StreamWriter):
            msg = pack_data(response,self._encrypt)
            await self.__send_by_sw(msg)
        elif isinstance(self.sender,WebSocketResponse):
            await self.__send_by_ws(msg)
        else:
            raise RuntimeError('Invalid sender, it must be an instance of StreamWriter or WebSocketResponse')
    
    async def __send_by_sw(self,msg:bytes):        
        w:StreamWriter = self.sender
        w.write(msg)
        await w.drain()

    async def __send_by_ws(self,msg:bytes):
        w:WebSocketResponse = self.sender
        await w.send_json(msg)


    def add_topic(self,topic:str):
        if topic not in self.topics:
            self.topics.append(topic)
 
    def remove_topic(self,topic:Union[str,list]):
        if type(topic) is list:
            for t in topic:
                self.remove_topic(t)
        else:
            if topic in self.topics:
                self.topics.remove(topic)


class SubscriptionContainer:
    """存放订阅者和订阅话题的容器"""
    __subscribes = dict()   # {客户端id1:{writer:writer,topics:[话题1,话题2,...]},客户端id2:{writer:writer,topics:[话题1,...]}}
    __topics = dict()       # {话题1:[客户端id1,客户端id2,..],话题2:[客户端id1,..]}        

    def has_sub(self,subId:str):
        if subId in self.__subscribes:
            return True
        return False

    def add_sub(self,cc:ClientConnection,topic:Union[str,list]=None):
        if cc.id not in self.__subscribes:
            self.__subscribes[cc.id] = cc
        if topic != None:
            self.add_topic(cc.id,topic)

    def add_sub_by_id(self,subId:str,sender:Union[StreamWriter,WebSocketResponse],topic:Union[str,list]=None):
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

    def add_topic(self,subId:str,topic:Union[str,list]):
        if type(topic) is list:
            for t in topic:
                self.add_topic(subId,t)
        else:
            s:ClientConnection = self.__subscribes.get(subId)
            if s:
                s.add_topic(topic)
                if topic not in self.__topics:
                    self.__topics[topic] = []
                if subId not in self.__topics[topic]:
                    self.__topics[topic].append(subId)


    def remove_topic(self,subId:str,topic:Union[str,list]):
        if type(topic) is list:
            for t in topic:
                self.remove_topic(subId,t)
        else:  
            s:ClientConnection = self.__subscribes.get(subId)
            subIds:list = self.__topics.get(topic) or []
            if s.id in subIds:
                self.__topics[topic].remove(s.id)
            if s:
                s.remove_topic(topic)

    def get_sub_by_id(self,subId:str)->ClientConnection:
        return self.__subscribes.get(subId)

    def get_subId_by_topic(self,topic:str)->list:
        """获取指定话题下所有的订阅者的id"""
        all_subId:list = self.__topics.get(topic)
        all_subId = all_subId or []
        return all_subId



async def process_request(request:dict,connection:ClientConnection,register:Register,sub_container:SubscriptionContainer)->bool:
    """处理请求总入口
    Union[RpcRequest,PubRequest,SubRequest,UnSubRequest]
    Returns:
        返回一个布尔值,是否结束连接
    """
    requestType = request.get('requestType')
    id = request.get("id")
    
    if UtRequestType.RPC.value==requestType:
        #  Rpc请求
        methodName = request.get("methodName")
        args = request.get("args")
        dicts = request.get("dicts")
        return await process_rpc_request(RpcRequest(id=id,methodName=methodName,args=args,dicts=dicts),connection,register)

    elif UtRequestType.UNSUBSCRIBE.value==requestType:
        # 取消订阅 topic        
        topics = request.get("topics")
        return await process_unsubscribe_request(UnSubRequest(id=id,topics=topics),connection,sub_container)

    elif UtRequestType.SUBSCRIBE.value==requestType:
        # 订阅 topic
        topics = request.get("topics")
        return await process_subscribe_request(SubRequest(id=id,topics=topics),connection,sub_container)

    elif UtRequestType.PUBLISH.value==requestType:
        topic = request.get("topic")
        msg = request.get("msg")
        return await process_publish_request(PubRequest(id=id,topic=topic,msg=msg),sub_container)

    else:
        # logging.log(f"处理请求时,出现不受支持的请求,请求的内容：{request}")
        return True


async def process_rpc_request(request:RpcRequest,connection:ClientConnection,register:Register)->bool:
    """
    # 处理rpc请求
    Args:
        request (dict): 请求体
        connection (ClientConnection): 客户端连接
        register (Register): 存放订阅者的容器

    ## request 请求体格式↓
    Attributes:
        id (int):  本次请求的id
        jsonrpc (str): 用于声明请求的类型，版本号2.0            
        method (str): 需要远程调用的方法名
        args (tuple): 元组参数
        dicts (dict): 字典参数

    样例:
        request = {
            'jsonrpc':'2.0',
            'id': 1,
            'method':method_name,
            'args':args,
            'dicts':dicts
        }

        
    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        jsonrpc (str): 用于声明请求的类型，版本号1.0
        method (str): 需要远程调用的方法名            
        result (dict): 执行结果
        state (str): failed / success
        error (str): 失败信息，执行失败时才会有该项

    样例:
        response = {
        'jsonrpc':'2.0',
        'id': 1,
        'method':method_name,
        'result':result,
        'state': 'success',
        'error':error
        }


    Returns:
        返回一个布尔值,是否结束连接

    """
    method_name:str = request.methodName
    args:tuple = request.args
    dicts:dict = request.dicts
    rm:RMethod = register.methods_of_rpc.get(method_name) if method_name else None
    response = UtResponse(id=request.id,
                          state=UtState.SUCCESS,
                          methodName=method_name,
                          responseType=request.requestType)

    if rm:
        state,result,error = await rm.execute(args,dicts)
        if state == UtState.FAILED:
            response.state = UtState.FAILED
            response.error = error
        else:
            response.result = result
    else:
        response.state = UtState.FAILED
        response.error = f'The rpc server does not have "{method_name}" methods. '
    
    await connection.send(response)
    return False


async def process_subscribe_request(request:SubRequest,connection:ClientConnection,sub_container:SubscriptionContainer)->bool:
    """
    # 处理subscribe订阅请求
    Args:
        request (SubRequest): 请求体            
        connection (ClientConnection): 客户端连接
        sub_container (SubscriptionContainer): 存放订阅者的容器

    ## request 请求体格式↓
    Attributes:
        id (int):  本次请求的id
        subscribe (str): 用于声明请求的类型，版本号1.0            
        topics (list[str]):  这是一个列表，可以订阅多个topic

    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        subscribe (str): 用于声明请求的类型，版本号1.0
        topics (list[str]):  这是一个列表，可以订阅多个topic
        state (str): failed / success
        error (str): 失败信息，订阅失败时才会有该项

    Returns:
        返回一个布尔值,是否结束连接

    """

    topics:list = request.topics
    
    response = UtResponse(id=connection.id,
                        responseType=UtRequestType.SUBSCRIBE,
                        state=UtState.SUCCESS)

    if not topics:
        response.error = '没有指定topic'
        await connection.send(response)
        return True
    else:
        if not sub_container.has_sub(connection.id):
            sub_container.add_sub(connection,topics)
        else:
            sub_container.add_topic(connection.id,topics)

        await connection.send(response)
        return False
    

async def process_unsubscribe_request(request:UnSubRequest,connection:ClientConnection,sub_container:SubscriptionContainer)->bool:
    """
    # 处理unsubscribe取消订阅请求
    Args:
        uid (str): 主体的uid
        request (dict): 请求体            
        hoding (bool): 是否处于订阅状态中
    
    ## request 请求体格式↓
    Attributes:
        id (int):  本次请求的id
        unsubscribe (str): 用于声明请求的类型，版本号1.0
        topics (list[str]):  这是一个列表，可以取消订阅多个topic

    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        unsubscribe (str): 用于声明请求的类型，版本号1.0
        topics (list[str]):  这是一个列表，可以取消订阅多个topic
        state (str): failed / success
        error (str): 失败信息，只有再非订阅状态才会失败
        
    Returns:
        返回一个布尔值,是否结束连接
    """

    topics:list = request.topics
    response =UtResponse(id=request.id,responseType=request.requestType,state=UtState.SUCCESS)

    if sub_container.has_sub(connection.id):
        sub_container.remove_topic(connection.id,topics)        
        await connection.send(response)
        return False
    else:
        response.state = UtState.FAILED
        response.error = '未订阅任何topic，请先成为订阅者'
        await connection.send(response)
        return True


async def process_publish_request(request:PubRequest,sub_container:SubscriptionContainer)->bool:
    """
    # 处理publish发布请求
    Args:
        uid (str): 主体的uid
        request (dict): 请求体
        
    ## request 请求体格式↓
    Attributes:
        publish (str): 用于声明请求的类型，版本号1.0
        topic (str): topic名称
        msg (dict): 发布的消息

    样例:
        request = {"publish":"1.0","topic":topic,"msg":msg}

    Returns:
        返回一个布尔值,是否结束连接
    """
    topic:str = request.topic
    msg:dict = request.msg

    # asyncio.sleep(0) 释放控制权，用于防止publish被持续不间断调用而导致的阻塞问题
    if not request.topic:
        # logging.warning(f"推送了一个空topic")
        asyncio.sleep(0)
        return True
    
    subIds:list = sub_container.get_subId_by_topic(topic)
    for subid in subIds:
        sub:ClientConnection = sub_container.get_sub_by_id(subid)
        if sub:await sub.send('publish',msg)
        
    asyncio.sleep(0)
    return False