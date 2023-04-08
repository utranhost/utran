
from multiprocessing import freeze_support
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import asyncio
import utran
from utran.server import Server,HttpResponse


server = Server()

@server.register.get('/')
async def home(name='wolrd'):
    return HttpResponse(text=f"<h3 style ='color: orange;'> Hello {name}.</h3>",content_type='text/html')

@server.register.rpc
@server.register.post
@server.register.get()
async def add(a:int,b:int):
    await asyncio.sleep(1)
    return a+b

@server.register.get(useProcess=True)
@server.register.rpc(useProcess=True)
async def add0(a:int,b:int):
    # await asyncio.sleep(3)
    return a+b

@server.register.get('/myclass',ins_kwds=dict(a=3,b=2),useProcess=True)
@server.register.rpc('myclass',ins_args=(1,3),useProcess=True)
class Myclass:
    def __init__(self,a,b) -> None:
        self.a = a
        self.b = b

    def get_result(self):
        return self.a + self.b

    def add(self,a:int,b:int):
        self.a = a
        self.b = b
        return a+b


@server.register.rpc
@server.register.get()
async def add2(d:dict):
    return d['a']+d['b']

@server.register.rpc
@server.register.get()
async def add3(l:list):
    return l[0]+l[1]

id = 0
@server.register.get
async def pub(topic:str,msg:str):
    global id
    id+=1
    await server.publish(id,msg,topic)




if __name__ == '__main__':
    freeze_support()
    utran.run(server)
