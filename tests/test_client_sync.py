import asyncio
import os
import time
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran
from utran.client.client import Client




client = Client()
# client.start()  # 不调用start方法时，会自启动

res = client.subscribe('good',lambda x,y:print(x,y))
print(res)

res= client.multicall(*[client.call(multicall=True).add(1,i) for i in range(0,20)],retransmitFull=False)        
print(res)


res = client.subscribe('good',lambda x,y:print(x,y))
print(res)

print("我要退出咯")
time.sleep(2)

client.exit()  # 无论是否有订阅，都需要手动退出