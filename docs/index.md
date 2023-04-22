# Utran快速入门

## 安装
```CMD title='pip安装'
pip install utran
```

## 服务器使用
```python title='服务端示例'
import utran
from utran.server import Server,HttpResponse

server = Server()

@server.register.get('/')
def sayhi():
    return HttpResponse(text="hi,Utran!",content_type='text/html')

@server.register.post
@server.register.rpc
async def add(a:int,b:int):
    return a+b

utran.run(server,host='127.0.0.1',port=8081,web_port=8080)

```



## 【服务端】
:::utran.Server

## 【客户端】
:::utran.Client

## 【运行器】
:::utran.run

