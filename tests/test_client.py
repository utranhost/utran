import asyncio
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.object import UtResponse
from utran.client import Client

client = Client(reconnectNum=3)

def on_topic(msg,topic):
    print(f"{topic}：",msg)


@client
async def main():    
    res = await client.subscribe('good',on_topic)
    print(res)

    res:UtResponse = await client.call('add300',dicts=dict(a=0,b=1),ignore=True)
    print(res)

    # print(r)

    res:UtResponse = await client.call('add',dicts=dict(a=0,b=2))
    print(res)

    res = await asyncio.gather(client.call('add511',dicts=dict(a=0,b=1),timeout=5,ignore=True),
                   client.call('add',dicts=dict(a=0,b=1),timeout=5),
                   client.call('add',dicts=dict(a=0,b=1),timeout=5),
                   client.call('add',dicts=dict(a=0,b=1),timeout=5),
                   client.call('add',dicts=dict(a=0,b=1),timeout=5))
    print(res)

    res:list[UtResponse] = await client.multicall(client.call('add0',args=[0,2],multicall=True),
                                                  client.call('add',dicts=dict(a=1,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=2,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=3,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=4,b=2),multicall=True),
                                                  client.call('ad3d',dicts=dict(a=5,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=6,b=2),multicall=True)
                                                  ,ignore=True)
    print(res)



    res = await client.unsubscribe('good')
    print(res)

    # await client.exit()

utran.run(client,uri='utran://127.0.0.1:8081')
