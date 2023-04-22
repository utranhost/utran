import asyncio
import os
import time
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client


client = Client()

@client
def main():
    res = client.subscribe('good',lambda x,y:print(x,y))
    print(res)

    res = client.call.myclass.add(1,2)
    print(res)

    res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
    print(res)

    client.unsubscribe('good')



print("\n","-"*30)


@client
def main2(thisclient:Client):
    res = thisclient.subscribe(['good','study'],[lambda msg,topic:print(msg,topic)]*2)
    print(res)

    t = time.time()
    res:list = thisclient.multicall(*[thisclient.call(multicall=True).add0(1,i) for i in range(10000)],ignore=True)
    # [thisclient.call.add(1,i) for i in range(100000)]
    print('res',time.time()-t)


    res = thisclient.call(ignore=True).ad0d(1,2)
    print(res)

    res = thisclient.call.add(1,5)
    print(res)

    res:list = thisclient.multicall(thisclient.call(multicall=True).add(1,2),
                                      thisclient.call(multicall=True).add(2,2),
                                      ignore=True)
    print(res)

    res = thisclient.unsubscribe(*['good','study'])
    print(res)