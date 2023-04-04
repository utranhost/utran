import asyncio
from typing import Union


from utran.client.baseclient import BaseClient
from utran.client.client import Client
from utran.server.rpcServer import RpcServer
from utran.server.server import Server
from utran.server.webserver import WebServer

from utran.utils import parse_utran_uri

def run(app:Union[Server,RpcServer,WebServer,BaseClient,Client],host:str='127.0.0.1',port:int=8081,web_port:int=8080,uri:str=None):
    """# 通用的运行器
    Args:
        app: 需要运行的服务
        host: 主机
        port: RPC端口
        web_port: WEB端口
        uri: 远程服务地址    
    """
    if isinstance(app,Server):asyncio.run(app.start(host=host,
                                                    web_port=web_port,
                                                    rpc_port=port))
        
    if isinstance(app,RpcServer):asyncio.run(app.start(host=host,
                                                       port=port))
        
    if isinstance(app,WebServer):asyncio.run(app.start(host=host,
                                                       port=web_port))
    
    if uri: 
        host,port = parse_utran_uri(uri)
    if isinstance(app,BaseClient):asyncio.run(app.start(host=host,
                                                    port=port))
