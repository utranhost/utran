# 客户端


## 【客户端】
```python title='使用示例'
import utran
from utran.client.client import Client

client = Client()

@client
async def main():
    res = await client.call(timeout=2).add(1,2)
    print(res)

    res:list = await client.multicall(client.call(multicall=True).add(1,2),
                                      client.call(multicall=True).add(2,2),
                                      ignore=True)
    print(res)


utran.run(client)
```
:::utran.client.client




## 【基础客户端】
```python title='使用示例'
import utran
from utran.client.baseclient import BaseClient

def on_topic(msg,topic):
    print(f"{topic}：",msg)

# 实例化，并指定断线重连次数为3次
client = BaseClient(reconnectNum=3)

@client
async def main():
    # 订阅话题
    res = await client.subscribe('good',on_topic)
    print(res)

    # 调用远程函数
    res = await client.call('add',dicts=dict(a=1,b=2))
    print(res)

    # 调用不存在的远程函数，ignore=True 忽略错误
    res = await client.call('add300',dicts=dict(a=0,b=1),ignore=True)
    print(res)

    # 合并多次调用
    res:list = await client.multicall(client.call('add',dicts=dict(a=1,b=2),multicall=True),
                                      client.call('add',dicts=dict(a=2,b=2),multicall=True),
                                      client.call('add',dicts=dict(a=3,b=2),multicall=True),
                                      client.call('add',dicts=dict(a=4,b=2),multicall=True),
                                      client.call('add300',dicts=dict(a=6,b=2),multicall=True)
                                      ,ignore=True)
    print(res)


    # 取消订阅话题
    res = await client.unsubscribe('good')
    print(res)

    # 退出程序
    # await client.exit()


if __name__ == "__main__":
    # 运行程序
    utran.run(client,uri='utran://127.0.0.1:8081')

```

:::utran.client.baseclient

## 【队列】
:::utran.client.que