
from abc import ABC, abstractmethod

from utran.register import Register
from utran.utils import SubscriptionContainer


class BaseServer(ABC):
    """
    # 服务器基类
        Args:
        host (str): 主机地址
        port (int): 端口号
        register (Register): 注册类，用于注册本地的可调用函数
        sub_container (SubscriptionContainer): 存放订阅者和订阅话题的容器
        severName (str): 服务名称
        dataMaxsize (int):  传输数据支持的最大字节数
        limitHeartbeatInterval (int): 心跳检测的极限值(单位为:秒)。为了防止心跳攻击，默认为1s,两次心跳的间隔小于该值则会断开连接。

    备注: 心跳需要客户端主动发起PING，服务端会被动响应PONG
    """

    def __init__(
            self,
            host: str,
            port: int,
            *,
            register: Register = None,
            sub_container: SubscriptionContainer = None,
            severName: str = 'Server',
            dataMaxsize: int = 102400,
            limitHeartbeatInterval: int = 1,
            dataEncrypt: bool = False) -> None:

        self._host = host
        self._port = port
        self._register = register or Register()
        self._sub_container = sub_container or SubscriptionContainer()
        self._severName = severName
        self._dataMaxsize = dataMaxsize
        self._dataEncrypt = dataEncrypt
        self._limitHeartbeatInterval = limitHeartbeatInterval

        self._server = None


    @abstractmethod
    async def start(self) -> None:
        """启动服务器"""
        pass

    @property
    def register(self) -> Register:
        """# 注册
        Returns:
            返回一个Register类的实例
        """
        return self._register
