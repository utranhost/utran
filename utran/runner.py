import asyncio
from typing import Union


from utran.client.baseclient import BaseClient
from utran.client.client import Client
from utran.server.server import Server
from utran.server.webserver import WebServer


def run(app:Union[Server,WebServer,BaseClient,Client],
        *,
        host:str='127.0.0.1',
        port:int=8080,
        url:str=None,
        entry:callable=None,
        loop:asyncio.AbstractEventLoop=None,
        username: str = None,
        password: str = None):
    """# 通用的运行器
    Args:
        app: 需要运行的服务
        host: 主机
        port: RPC端口
        web_port: WEB端口
        url: 远程服务地址    
        loop: 指定事件循环
    """

    if isinstance(app,Server):        
        coro= app.start(host=host,
                port=port,
                username=username,
                password=password)
        if loop:
            loop.run_until_complete(coro)
        else:
            asyncio.run(coro)
        

    if isinstance(app,WebServer):
        coro= app.start(host=host,
                port=port,
                username=username,
                password=password)
        if loop:
            loop.run_until_complete(coro)
        else:
            asyncio.run(coro)
    

    if isinstance(app,Client):
        if callable(entry):
            app(entry,url=url,username=username,password=password,loop=loop)
        else:
            raise RuntimeError('Run Error,未指定有效的entry')
        
