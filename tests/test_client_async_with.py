import os
import time,asyncio
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))

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



