import asyncio
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client

client = Client(uri='utran://127.0.0.1:8081')
res = client.call.add(1,2)
print(res)

res = client.call.myclass.add(23,7890)
print(res)

res = client.call.myclass.get_result()
print(res)

res = client.call.add(1454,2)
print(res)

res:list = client.multicall(client.call(multicall=True).add(1,2),
                            client.call(multicall=True).add0(2,2),
                            client.call(multicall=True).add(3,2),
                            client.call(multicall=True).add(4,2),
                            ignore=True)
print(res)
