# utran

## 安装
```CMD title='pip安装'
pip install utran
```

## 创建服务器
```python title='服务端示例'
import utran
from utran.server import Server,HttpResponse

server = Server()

@server.register.get('/')
def sayhi():
    return HttpResponse(text="hi,Utran!",content_type='text/html')


@server.register.rpc
async def add(a:int,b:int):
    return a+b

utran.run(server,host='127.0.0.1',port=8081,web_port=8080)

```

## 客户端1（同步调用）
```python title='客户端示例'
import utran

client = utran.Client(url='ws://127.0.0.1:8081')
res = client.call.add(1,2)
print(res)

client.exit()
```

## 客户端2（同步调用）
```python title='客户端示例'
import utran

client = utran.Client(url='ws://127.0.0.1:8081')

@client
def main():
    res = client.call.add(1,2)
    print(res)

```

## 客户端3（异步调用）
```python title='客户端示例'
import utran

client = utran.Client(url='ws://127.0.0.1:8081')

@client
async def main():
    res = await client.call.add(1,2)
    print(res)

```

## 客户端4（同步调用）
```python title='客户端示例'
import utran

with utran.Client(url='ws://127.0.0.1:8081') as client:
    res = client.call.add(1,2)
    print(res)

```

## 客户端5（异步调用）
```python title='客户端示例'
import utran

async with utran.Client(url='ws://127.0.0.1:8081') as client:
    res = await client.call.add(1,2)
    print(res)

```