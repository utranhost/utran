import asyncio
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client



def on_topic(msg,topic):
    print(f"{topic}：",msg)



client = utran.Client(url='ws://127.0.0.1:8080')

@client
async def main():
    res = await client.subscribe(['good','study'],[on_topic]*2)
    print(res)
    res = await client.call.myclass.add(23,7890)
    print(res)

    res = await client.call.myclass.get_result()
    print(res)
    # await client.exit()

    res = await client.call.add0(1,2) # 无选项调用
    print(res)

    res = await client.call(timeout=10).add(1,2)  # 有选项调用
    print(res)

    res = await client.call.myclass.get_result()  # 类的访问
    print(res)

    res = await client.call.myclass.add(12,2)  # 类的访问
    print(res)


    res:list = await client.multicall(client.call(multicall=True).add(1,2),
                                      client.call(multicall=True).add(2,2),
                                      ignore=True)
    print(res)

    res = await client.unsubscribe(*['good','study'])
    print(res)
    # await client.exit()


print("\n","-"*30)


@client
async def main(this:Client):
    res = await this.subscribe('good',lambda x,y:print(x,y))
    print(res)

    res = await this.call.myclass.add(1,2)
    print(res)

    res= await this.multicall(*[this.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
    print(res)

    await this.unsubscribe('good')