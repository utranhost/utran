import asyncio
from typing import Union

from utran.handler import process_publish_request
from utran.register import Register
from utran.server.webserver import WebServer
from utran.server.rpcServer import RpcServer

from utran.utils import SubscriptionContainer



class Server:
    """服务端支持 jsonrpc、GET、POST、sub/pub
    Args:
        host (str): 主机地址
        port (int): 端口号
        severName (str): 服务名称
        checkParams (bool): 调用注册函数或方法时，是否检查参数类型，开启后当类型为数据模型时可以自动转换
        checkReturn (bool): 调用注册函数或方法时，是否检查返回值类型，开启后当类型为数据模型时可以自动转换
        dataMaxsize (int):  支持最大数据字节数
        limitHeartbeatInterval (int): 心跳检测的极限值，为了防止心跳攻击，默认为1s,两次心跳的间隔小于该值则会断开连接。
    """
    __slots__=(
        '_host',
        '_web_port',
        '_rpc_port',
        '_is_run_webserver',
        '_is_run_rpcserver',
        '_checkParams',
        '_checkReturn',
        '_register',
        '_sub_container',
        '_severName',
        '_dataMaxsize',
        '_dataEncrypt',
        '_limitHeartbeatInterval',
        '_webServer',
        '_rpcServer',
        '__isruning')
    
    def __init__(
            self,            
            *,
            host: str = '127.0.0.1',
            web_port:int=8080,
            rpc_port: int=8081,
            is_run_webserver:bool =True,
            is_run_rpcserver:bool =True,
            checkParams:bool = True,
            checkReturn:bool = True,
            register: Register = None,
            sub_container: SubscriptionContainer = None,
            severName: str = 'UtranServer',
            dataMaxsize: int = 102400,
            limitHeartbeatInterval: int = 1,
            dataEncrypt: bool = False) -> None:


        assert is_run_rpcserver or is_run_webserver,"There must be a service running."

        self._host = host
        self._web_port= web_port
        self._rpc_port = rpc_port
        self._is_run_webserver = is_run_webserver
        self._is_run_rpcserver = is_run_rpcserver
        self._checkParams = checkParams
        self._checkReturn = checkReturn
        self._register = register or Register(checkParams,checkReturn)
        self._sub_container = sub_container or SubscriptionContainer()
                
        self._severName = severName
        self._dataMaxsize = dataMaxsize        
        self._limitHeartbeatInterval = limitHeartbeatInterval
        self._dataEncrypt = dataEncrypt

        self._webServer = WebServer(
            host,
            web_port,
            register= self._register, 
            sub_container= self._sub_container,
            dataMaxsize= self._dataMaxsize, 
            limitHeartbeatInterval= self._limitHeartbeatInterval, 
            dataEncrypt= self._dataEncrypt) if is_run_webserver else None

        self._rpcServer = RpcServer(
            host,
            rpc_port,
            register= self._register, 
            sub_container= self._sub_container,
            dataMaxsize= self._dataMaxsize, 
            limitHeartbeatInterval= self._limitHeartbeatInterval, 
            dataEncrypt= self._dataEncrypt) if is_run_rpcserver else None
        
        self.__isruning=False

    async def start(self)->None:
        """
        # 运行服务
        示例:
            ### server = Server()
            ### asyncio.run(server.run())
        """
        if self.__isruning: return
        else: self.__isruning = True
        
        t = [s.start() for s in [self._webServer,self._rpcServer] if s!=None]
        await asyncio.gather(*t)


    @property
    def register(self)->Register:
        """# 注册
        Returns:
            返回一个Register类的实例
        """
        return self._register


    async def publish(self,topic:str,msg:dict)->None:
        """
        # 给指定topic推送消息
        Args:
            topic (str): 指定话题
            msg (dict): 消息
        """
        await process_publish_request(dict(topic=topic,msg=msg),self._sub_container)


def run(server:Union[Server,RpcServer,WebServer]):
    """启动服务"""
    asyncio.run(server.start())

