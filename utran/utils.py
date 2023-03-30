from asyncio import StreamWriter
import uuid

import ujson
from typing import List, Union

from aiohttp.web_ws import WebSocketResponse
from utran.object import UtResponse


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


class ClientConnection:
    """客户端连接"""
    __slots__=('topics','sender','__id','_encrypt')
    def __init__(self,sender:Union[StreamWriter,WebSocketResponse],encrypt:bool=False):
        self.topics = []
        self.__id = str(uuid.uuid4())
        self.sender = sender
        self._encrypt=encrypt

    @property
    def id(self):
        return self.__id

    async def send(self,response:UtResponse):
        if isinstance(self.sender,StreamWriter):
            msg = pack_data(response,self._encrypt)
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


