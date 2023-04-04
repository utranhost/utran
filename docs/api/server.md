
# 服务端模块


## 【完整服务端】
```python title='RpcServer使用示例'
import utran
from utran.server import Server,HttpResponse


server = Server()

@server.register.get('/')
async def home(name='wolrd'):
    return HttpResponse(text=f"<h3 style ='color: orange;'> Hello {name}.</h3>",content_type='text/html')

@server.register.rpc
@server.register.post
@server.register.get
async def add(a:int,b:int):
    return a+b

@server.register.rpc
async def hardwork(a:int,b:int):
    await asyncio.sleep(1)
    return a+b

id = 0
@server.register.get
async def pub(topic:str,msg:str):
    global id
    id+=1
    await server.publish(id,msg,topic)


utran.run(server,host='127.0.0.1',port=8081,web_port=8080)

```
::: utran.server.Server






## 【Rpc服务端】
```python title='RpcServer使用示例'
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

```
::: utran.server.RpcServer





## 【Web服务端】
```python title='WebServer使用示例'
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
```
::: utran.server.WebServer




## 【服务端基类】
::: utran.server.baseServer