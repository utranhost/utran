import asyncio

from utran.handler import process_publish_request
from utran.object import UtRequest, UtType
from utran.register import Register
from utran.server.webserver import WebServer
from utran.server.rpcServer import RpcServer

from utran.object import SubscriptionContainer



class Server:
    """包含了web服务和Rpc服务端，支持 RPC、GET、POST、SUB/PUB
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
        '_without_webserver',
        '_without_rpcserver',
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
            without_webserver:bool =False,
            without_rpcserver:bool =False,
            checkParams:bool = True,
            checkReturn:bool = True,
            register: Register = None,
            sub_container: SubscriptionContainer = None,
            severName: str = 'UtranServer',
            dataMaxsize: int = 102400,
            limitHeartbeatInterval: int = 1,
            dataEncrypt: bool = False) -> None:


        assert not without_rpcserver or not without_webserver,"There must be a service running."

        self._without_webserver = without_webserver
        self._without_rpcserver = without_rpcserver
        self._checkParams = checkParams
        self._checkReturn = checkReturn
        self._register = register or Register(checkParams,checkReturn)
        self._sub_container = sub_container or SubscriptionContainer()
                
        self._severName = severName
        self._dataMaxsize = dataMaxsize        
        self._limitHeartbeatInterval = limitHeartbeatInterval
        self._dataEncrypt = dataEncrypt
        
        self.__isruning=False


    async def start(self,
                    host: str = '127.0.0.1',
                    web_port:int=8080,
                    rpc_port: int=8081)->None:
        """
        # 运行服务
        示例:
            ### server = Server()
            ### asyncio.run(server.start())
        """

        if self.__isruning: return
        else: self.__isruning = True

        self._host = host
        self._web_port= web_port
        self._rpc_port = rpc_port
        self._webServer = WebServer(
            register= self._register, 
            sub_container= self._sub_container,
            dataMaxsize= self._dataMaxsize, 
            limitHeartbeatInterval= self._limitHeartbeatInterval, 
            dataEncrypt= self._dataEncrypt) if not self._without_webserver else None

        self._rpcServer = RpcServer(
            register= self._register, 
            sub_container= self._sub_container,
            dataMaxsize= self._dataMaxsize, 
            limitHeartbeatInterval= self._limitHeartbeatInterval, 
            dataEncrypt= self._dataEncrypt) if not self._without_rpcserver else None
                
        t = []
        if not self._without_rpcserver: t.append(self._rpcServer.start(host,rpc_port))
        if not self._without_webserver: t.append(self._webServer.start(host,web_port))
        await asyncio.gather(*t)


    @property
    def register(self)->Register:
        """# 注册
        Returns:
            返回一个Register类的实例
        """
        return self._register


    async def publish(self,id:int,msg:any,*topics:str)->None:
        """
        # 给指定topic推送消息
        Args:
            id (int): id标识
            topic (str): 指定话题
            msg (dict): 消息
        """ 
        await process_publish_request(UtRequest(id,requestType=UtType.PUBLISH,topics=topics,msg=msg),self._sub_container)


