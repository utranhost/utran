

import asyncio
import time
from typing import Union
import ujson
from utran.handler import process_publish_request, process_request
from utran.log import logger

from utran.object import HeartBeat, UtRequest, create_UtRequest
from utran.register import Register
from utran.server.baseServer import BaseServer
from utran.object import ClientConnection, SubscriptionContainer
from utran.utils import unpack_data2_utran


class RpcServer(BaseServer):
    """服务端支持 rpc、sub/pub"""
    __slots__=tuple()
    def __init__(self,
            *,
            register: Register = None,
            sub_container: SubscriptionContainer = None,
            severName: str = 'RpcServer',
            dataMaxsize: int = 102400,
            limitHeartbeatInterval: int = 1,
            dataEncrypt: bool = False) -> None:
        
        super().__init__(
            register=register, 
            sub_container=sub_container, 
            severName=severName, 
            dataMaxsize=dataMaxsize, 
            limitHeartbeatInterval=limitHeartbeatInterval, 
            dataEncrypt=dataEncrypt)


    async def start(self,host: str,port: int,) -> None:
        """
        # 运行服务
        示例:
            ### server = Server()
            ### asyncio.run(server.start())
        """
        if self._server != None: return
        self._host = host
        self._port = port
        self._server = await asyncio.start_server(self.__handle_client, self._host, self._port)
        logger.success(f"\n{'='*6} {self._severName} started on {self._host}:{self._port} {'='*6}")


    async def publish(self, topic: str, msg: dict) -> None:
        """
        # 给指定topic推送消息
        Args:
            topic (str): 指定话题
            msg (dict): 消息
        """
        await process_publish_request(dict(topic=topic, msg=msg), self._sub_container)


    async def __handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        buffer = b''
        connection = ClientConnection(writer, self._dataEncrypt)
        t = float('-inf')
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    # 收到空消息时，退出，同时清理订阅
                    logger.debug(f'收到空消息，断开连接')
                    break

                # 心跳检测
                if data == HeartBeat.PING.value:
                    # print("PING")
                    if time.time() - t < self._limitHeartbeatInterval:
                        logger.debug(f'两次心跳得时间间隔小于{self._limitHeartbeatInterval}s，强制断开连接。')
                        break   # 当两次心跳得时间间隔小于1s，强制断开连接。

                    writer.write(HeartBeat.PONG.value)
                    await writer.drain()
                    t = time.time()
                    continue

                try:
                    requestName, request, buffer = unpack_data2_utran(
                        data, buffer, self._dataMaxsize)
                    if request is None:
                        continue
                    
                    request: str = request.decode('utf-8')
                    requestName:str = requestName.decode('utf-8')
                    res: Union[dict,list] = ujson.loads(request)

                except Exception as e:
                    logger.debug(f'收客户端数据，拆包时异常:{e}')
                    break

                # 处理请求
                if await process_request(create_UtRequest(res,res.get('id'),res.get('encrypt')), connection, self._register, self._sub_container):
                    break

            self._sub_container.del_sub(connection.id)
            try:
                writer.write(b'')
                await writer.drain()
                writer.close()
            except Exception as e:
                logger.debug(f'通知关闭连接时异常:{e}')

        except ConnectionResetError:
            self._sub_container.del_sub(connection.id)
            logger.debug(f'客户端:{connection.id},连接丢失已断开.')