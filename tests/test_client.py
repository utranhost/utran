import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


from utran.object import UtResponse
from utran.client.baseclient import Client,run

client = Client()

def on_topic(msg):
    print(msg)

async def main():
    res:UtResponse = await client.call('add',dicts=dict(a=0,b=1))
    print(res)

    res:UtResponse = await client.call('add',dicts=dict(a=0,b=2))
    print(res)


    res:list[UtResponse] = await client.multicall(client.call('add',args=[0,2],multicall=True),
                                                  client.call('add',dicts=dict(a=1,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=2,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=3,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=4,b=2),multicall=True),
                                                  client.call('ad3d',dicts=dict(a=5,b=2),multicall=True),
                                                  client.call('add',dicts=dict(a=6,b=2),multicall=True)
                                                  )
    print(res)

    res = await client.subscribe('good',on_topic)
    print(res)

    # await client.exit()

run(client.run('utran://127.0.0.1:8081',main()))

