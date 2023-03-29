import os
os.sys.path.append(os.path.abspath('./'))


import utran
from utran.server import Server,HttpResponse


server = Server()

@server.register.get('/')
async def home(name='wolrd'):
    return HttpResponse(text=f"<h3 style ='color: orange;'> Hello {name}.</h3>",content_type='text/html')

@server.register.rpc
@server.register.get()
async def add(a:int,b:int):
    return a+b

@server.register.rpc
@server.register.get()
async def add2(d:dict):
    return d['a']+d['b']

@server.register.rpc
@server.register.get()
async def add3(l:list):
    return l[0]+l[1]

utran.run(server)
