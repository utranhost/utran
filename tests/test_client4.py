import asyncio
import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client




with Client(uri='utran://127.0.0.1:8081') as client:
    res = client.subscribe(['good','study'],lambda x:print(x))
    print(res)

    res = client.call.add(1,2)
    print(res)

    res = client.call.add(1,5)
    print(res)

    res = client.call.add0(6,5)
    print(res)

    res = client.call.add0(1,2)
    print(res)

    res = client.call.add0(1,5)
    print(res)

    res = client.call.add0(6,5)
    print(res)