import asyncio
import os,time
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client


with Client() as client:
    res = client.subscribe('good',lambda x,y:print(x,y))
    res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,100)],retransmitFull=False)
    print(res)
    time.sleep(1)
    # client.exit()
    res = client.unsubscribe('good')


print('\n',"--"*30)

with Client(url='ws://127.0.0.1:8080') as client:
    res = client.subscribe(['good','study'],[lambda msg,topic:print(msg,topic)]*2)
    print(res)

    res = client.call.add(1,2)
    print(res)

    res = client.call.add(1,5)
    print(res)

    res = client.call.add0(6,5)
    print(res)

    res = client.call.add0(1,2)
    print(res)

    res:list = client.multicall(client.call(multicall=True).add(1,2),
                                client.call(multicall=True).add(2,2),
                                ignore=True)
    print(res)

    res = client.unsubscribe(*['good','study'])
    print(res)