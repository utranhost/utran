import asyncio
import contextvars
import os
import threading
import time
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.baseclient import BaseClient


async def main():
    async with BaseClient(maxReconnectNum=3) as client:
        
        res = await client.subscribe('good',lambda x,y:print(x,y))

        res = await client.call('add0',[1,3])
        print(res)

        res= await client.multicall(*[client.call("add",[1,i],multicall=True) for i in range(0,20)],retransmitFull=False)        
        print(res)

        res = await client.unsubscribe('good')
        # print(res)
        # await client.exit()



asyncio.run(main())



