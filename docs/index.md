# Utran


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

utran.run(server)

```



```python title='Utran协议'
rpc/subscribe/unsubscribe/publish
length:xx
encrypt:0/1
message_json

```