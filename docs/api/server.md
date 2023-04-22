
# 服务端模块


## 【服务端】
```python title='RpcServer使用示例'
import utran
from utran.server import Server,HttpResponse


server = Server()

@server.register.get('/')
async def home(name='wolrd'):
    return HttpResponse(text=f"<h3 style ='color: orange;'> Hello {name}.</h3>",content_type='text/html')

@server.register.rpc(useProcess=True)   # 添加注册选项， useProcess=True为在子进程中执行
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


utran.run(server,host='127.0.0.1',port=8081,port=8080)

```
::: utran.server.Server



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

utran.run(server,host='127.0.0.1',port=8080)
```
::: utran.server.WebServer




## 【服务端基类】
::: utran.server.baseServer