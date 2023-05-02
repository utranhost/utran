import asyncio
import os
import time
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client


# async call
async def main(client:Client):
    res = await client.subscribe('good',lambda x,y:print(x,y))
    print(res)

    res = await client.call.myclass.add(1,2)
    print(res)

    res= await client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,50)],retransmitFull=False)        
    print(res)

    res = await client.callByname('add',[1,3])
    print("callByname:",res)

    res= await client.multicall(*[client.callByname('add',[1,i],multicall=True) for i in range(0,50)])
    print("callByname:",res)

    await client.unsubscribe('good')


utran.run(Client(),entry=main)


print('\n',"--"*50)



# sync call
def main(client:Client):
    res = client.subscribe('good',lambda x,y:print(x,y))
    print(res)

    res = client.call.myclass.add(1,2)
    print(res)

    res = client.callByname('add',[1,3])
    print("callByname:",res)

    res= client.multicall(*[client.callByname('add',[1,i],multicall=True) for i in range(0,50)])
    print("callByname:",res)

    res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,200)],retransmitFull=False)        
    print(res)

    client.unsubscribe('good')


utran.run(Client(),entry=main,url='ws://127.0.0.1:8080')




