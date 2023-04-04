import asyncio
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client

client = Client()

@client
async def main():
    
    res = await client.call.add(1,2) # 无选项调用
    print(res)

    res = await client.call(timeout=1).add(1,2)  # 有选项调用
    print(res)

    res:list = await client.multicall(client.call(multicall=True).add(1,2),
                                      client.call(multicall=True).add(2,2),
                                      ignore=True)
    print(res)


utran.run(client)