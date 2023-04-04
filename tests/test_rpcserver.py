import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.server import RpcServer

server = RpcServer()

@server.register.rpc
async def add(a:int,b:int):
    return a+b

@server.register.rpc
async def sub(a:int,b:int):
    return a-b

utran.run(server,host='127.0.0.1',port=8081)
