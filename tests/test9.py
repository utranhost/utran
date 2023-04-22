import asyncio
import threading
import aiohttp


class Client:
    def __init__(self) -> None:
        # self.session = aiohttp.ClientSession()
        pass

    async def start(self):
        self.session = aiohttp.ClientSession()
        await self.connect()

    async def connect(self):
        ws = await self.session.ws_connect('ws://127.0.0.1:8080',auth=aiohttp.BasicAuth('utranhost','utranhost'))
        await ws.send_str('Hello, world!')
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                print(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

def run_in_thread(client:Client):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.start())

client = Client()
thread = threading.Thread(target=run_in_thread,args=(client,))
thread.start()