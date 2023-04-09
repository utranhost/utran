import asyncio
import concurrent.futures
import threading
import time

class Test:

    def __init__(self,name:str) -> None:
        self.unx = name

    async def say(self,msg:str):
        return f'{msg},{self.unx}!'

    async def modfy(self,name:str):
        self.unx = name

    async def timer(self,msg):
        while True:            
            print(msg)
            await asyncio.sleep(1)

async def coro():
    print('coroutine started')
    await asyncio.sleep(1)
    print('coroutine finished')





def worker(loop):
    print('worker started')
    loop.run_forever()
    print('worker finished')

def main():
    loop = asyncio.new_event_loop()
    test = Test('ikale')
    t = threading.Thread(target=worker, args=(loop,))
    t.start()
    
    future = asyncio.run_coroutine_threadsafe(test.say('hi'), loop)
    print(future.result())

    asyncio.run_coroutine_threadsafe(test.timer('---'), loop)

    asyncio.run_coroutine_threadsafe(test.modfy('chaozai'), loop)
    future = asyncio.run_coroutine_threadsafe(test.say('hello'), loop)
    print(future.result())

    time.sleep(6)
    future = asyncio.run_coroutine_threadsafe(test.say('hi'), loop)
    print(future.result())

    # print(,test.unx)
    t.join()
    loop.close()

if __name__ == '__main__':
    main()