import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


from utran.object import UtResponse
from utran.client.baseclient import Client,run

client = Client()

async def main():
    res:UtResponse = await client.call('add',a=1,b=2)
    print(res.to_dict())

    res:UtResponse = await client.call('add',a=7,b=2)
    print(res.to_dict())


run(client.run('utran://127.0.0.1:8081',main()))
