import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.server import WebServer,HttpResponse


server = WebServer()

@server.register.get('/')
async def home(name='utran'):
    return HttpResponse(text=f"<h1'> Hello {name}.</h1>",content_type='text/html')


@server.register.post
async def add(a:int,b:int):
    return a+b

utran.run(server,host='127.0.0.1',web_port=8080)
