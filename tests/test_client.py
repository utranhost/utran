import asyncio
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.baseclient import BaseClient

client = BaseClient(reconnectNum=3,serverTimeout=2)

def on_topic(msg,topic):
    print(f"{topic}：",msg)


@client
async def main():
    res = await client.subscribe(['good','study'],on_topic)
    print(res)

    res = await client.call('add',dicts=dict(a=7,b=1))
    print(res)

    res = await client.call('myclass.add',dicts=dict(a=9,b=1))
    print(res)

    res = await client.call('add300',dicts=dict(a=0,b=1),ignore=True)
    print(res)

    # # print(r)

    res = await client.call('add0',dicts=dict(a=0,b=2),timeout=300000)
    print(res)

    # res = await asyncio.gather(client.call('add',dicts=dict(a=0,b=1),timeout=5,ignore=False),
    #                client.call('add511',dicts=dict(a=0,b=1),timeout=5000000000000,ignore=True),
    #                client.call('add',dicts=dict(a=0,b=1),timeout=5),
    #                client.call('add511',dicts=dict(a=0,b=1),timeout=5,ignore=True),
    #                client.call('add',dicts=dict(a=0,b=1),timeout=5),
    #                client.call('add',dicts=dict(a=0,b=1),timeout=5,ignore=False),
    #                client.call('add511',dicts=dict(a=0,b=1),timeout=5,ignore=True),
    #                client.call('add',dicts=dict(a=0,b=1),timeout=5),
    #                client.call('add511',dicts=dict(a=0,b=1),timeout=5,ignore=True),
    #                client.call('add',dicts=dict(a=0,b=1),timeout=1000000000000000000000000000)
    #                )
    # print(res)

    res:list = await client.multicall(client.call('add',args=[0,2],multicall=True),
                                    client.call('add',dicts=dict(a=1,b=2),multicall=True),
                                    client.call('add',dicts=dict(a=2,b=2),multicall=True),
                                    client.call('add',dicts=dict(a=3,b=2),multicall=True),
                                    client.call('add',dicts=dict(a=4,b=2),multicall=True),
                                    client.call('ad3d',dicts=dict(a=5,b=2),multicall=True),
                                    client.call('add',dicts=dict(a=6,b=2),multicall=True)
                                    ,ignore=True)
    print(res)

    res:list = await client.multicall(client.call('add0',args=[0,2],multicall=True),
                                      client.call('add0',args=[1,2],multicall=True),
                                      client.call('add0',args=[2,2],multicall=True),
                                    client.call('add0',dicts=dict(a=1,b=2),multicall=True),
                                    ignore=True)
    print(res)

    # res = await client.unsubscribe('good','study2') #!!!!!!!!!!!!!!!!!!!最大嫌疑!!!!!!!!!!!!!!!!!!!!!!!!
    # print(res)
    # print(asyncio.all_tasks())
    # res = await client.unsubscribe('good255')
    # print(res)
    # print(asyncio.all_tasks())
    res = await client.subscribe(['good7','study7'],on_topic)
    print(res)
    # await client.exit()

utran.run(client,uri='utran://127.0.0.1:8081')
