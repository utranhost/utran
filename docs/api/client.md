# 客户端


## 【客户端】
同步调用方式会将服务启动到一个子线程中。异步调用不会使用子线程来运行服务
#### 示例1 （同步调用）
这种调用方式无论是否有订阅，都需要手动调用exit方法退出
```python title='使用示例3'
import utran
from utran.client.client import Client

client = Client()
# client.start()  # 不调用start方法时，会自启动

res = client.subscribe('good',lambda x,y:print(x,y))
print(res)

res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
print(res)

res = client.unsubscribe('good')
print(res)

client.exit()  # 无论是否有订阅，都需要手动退出

```


### 装饰器用法
装饰器用法，在main函数执行完毕后，如果有订阅的会自动等待推送，订阅为空时会自动退出
#### 示例1（同步调用）

```python title='使用示例1'
import utran
from utran.client.client import Client

client = Client(url='ws://127.0.0.1:8080')

@client
def main():
    res = client.subscribe('good',lambda x,y:print(x,y))
    print(res)

    res = client.call.myclass.add(1,2)
    print(res)

    res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
    print(res)

    client.unsubscribe('good')


```
#### 示例2 （异步调用）
```python title='使用示例2'
import utran
from utran.client.client import Client

client = Client(url='ws://127.0.0.1:8080')

@client
async def main():
    
    res = await client.call.add(1,2) # 无选项调用
    print(res)

    res = await client.call(timeout=1).add(1,2)  # 有选项调用
    print(res)

    res:list = await client.multicall(client.call(multicall=True).add(1,2),
                                      client.call(multicall=True).add(2,2),
                                      ignore=True)
    print(res)


```
### 使用with关键 （同步调用）
使用逻辑与指定入口的方式一致
#### 示例1（同步调用）
```python title='使用示例2'
import utran
from utran.client.client import Client

with Client(url='ws://127.0.0.1:8080') as client:
    res = client.subscribe(['good','study'],lambda msg,topic:print(msg,topic))
    print(res)

    res = client.call.add0(6,5)
    print(res)

    res = client.call.add0(1,2)
    print(res)

    res = client.unsubscribe(*['good','study'])
    print(res)
```

#### 示例2 （异步调用）
```python title='使用示例2'
import utran
from utran.client.client import Client

async def main():
    async with Client() as client:
        res = await client.subscribe('good',lambda x,y:print(x,y))
        res= await client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,100)],retransmitFull=False)
        print(res)
        # time.sleep(1)
        # await client.exit()
        res = await client.unsubscribe('good')

asyncio.run(main())
```



### run用法，指定入口
```python title='使用示例2'
from utran.client.client import Client

# async call
async def main(client:Client):
    res = await client.call.myclass.add(1,2)
    print(res)

utran.run(Client(),entry=main)

print('\n',"--"*50)

# sync call
def main(client:Client):
    res = client.call.myclass.add(1,2)
    print(res)

utran.run(Client(),entry=main,url='ws://127.0.0.1:8080')
```





:::utran.client.client




## 【基础客户端】
```python title='使用示例'
import utran
from utran.client.baseclient import BaseClient

def on_topic(msg,topic):
    print(f"{topic}：",msg)

# 实例化，并指定断线重连次数为3次
bsclient = BaseClient(maxReconnectNum=3)

async def main():
    # 订阅话题
    res = await bsclient.subscribe('good',on_topic)
    print(res)

    # 调用远程函数
    res = await bsclient.call('add',dicts=dict(a=1,b=2))
    print(res)

    # 调用不存在的远程函数，ignore=True 忽略错误
    res = await bsclient.call('add300',dicts=dict(a=0,b=1),ignore=True)
    print(res)

    # 合并多次调用
    res:list = await bsclient.multicall(bsclient.call('add',dicts=dict(a=1,b=2),multicall=True),
                                      bsclient.call('add',dicts=dict(a=2,b=2),multicall=True),
                                      bsclient.call('add',dicts=dict(a=3,b=2),multicall=True),
                                      bsclient.call('add',dicts=dict(a=4,b=2),multicall=True),
                                      bsclient.call('add300',dicts=dict(a=6,b=2),multicall=True)
                                      ,ignore=True)
    print(res)


    # 取消订阅话题
    res = await bsclient.unsubscribe('good')
    print(res)

    # 退出程序
    # await bsclient.exit()


if __name__ == "__main__":
    # 运行程序
    asyncio.run(main())

```

:::utran.client.baseclient
