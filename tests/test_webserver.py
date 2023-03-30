import os
os.sys.path.append(os.path.abspath('./'))


import utran
from utran.server import WebServer,HttpResponse


server = WebServer(host='127.0.0.1',port=8080)

@server.register.get('/')
async def home(name='wolrd'):
    return HttpResponse(text=f"<h3 style ='color: orange;'> Hello {name}.</h3>",content_type='text/html')

@server.register.rpc
@server.register.post
async def add(a:int,b:int):
    return a+b

utran.run(server)
