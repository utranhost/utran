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

    res= await client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
    print(res)

    await client.unsubscribe('good')


utran.run(Client(),entry=main)


print('\n',"--"*50)



# sync call
def main(client:Client):
    res = client.subscribe('good',lambda x,y:print(x,y))
    print(res)

    res = client.call.myclass.add(1,2)
    print(res)

    res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
    print(res)

    client.unsubscribe('good')


utran.run(Client(),entry=main,url='ws://127.0.0.1:8080')




