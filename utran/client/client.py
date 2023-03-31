import asyncio
import json
import socket
import zlib

from utils import (pack_data2_utran,
                   unpack_data2_utran)
from utran.client.que import ResultQueue


REQUEST_ID:int=0
def gen_request(requestType,method_name,args,dicts)->dict:
    global REQUEST_ID
    """生成请求"""
    REQUEST_ID += 1    
    return pack_data2_utran(requestType,{requestType:'2.0', 'id': REQUEST_ID, 'method':method_name, 'args':args, 'dicts':dicts})





class SyncClient:
    def __init__(self,host='localhost', port=8080) -> None:
        self.__host = host
        self.__port = port
        self.__reslutqueue = ResultQueue()
        self.__id = 0
        self._isconnected=False
        self._buffer = b''


    def connect(self):
        """连接服务端"""
        if self._isconnected:
            return

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((self.__host, self.__port))
        self._isconnected = True


    def call(self,method_name,*args,**dicts):
        """远程调用"""
        request:dict = self.gen_request(method_name,args,dicts)
        request_packet = pack_data2_utran('jsonrpc',request)
        self.__socket.sendall(request_packet)
        try:
            while True:
                chunk = self.__socket.recv(1024)
                if not chunk:
                    raise ConnectionError('Connection closed by server')
                name,message, self._buffer = unpack_data2_utran(chunk, self._buffer)
                
                if message is not None:
                    response:dict = json.loads(message.decode('utf-8').strip())
                    self.__reslutqueue.push(response)
                    
                response = self.__reslutqueue.pull(request['id'])
                if response:
                    return response
                
        except Exception as e:
            self.close()
            raise e


    def close(self):
        """关闭"""
        if self.__socket:
            try:
                self.__socket.sendall('')  # 发送空信息，告诉服务端关闭连接                
            except:
                try:
                    self.__socket.shutdown(socket.SHUT_RDWR)  # 关闭读和写
                except OSError:
                    pass
            finally:
                self.__socket.close()
                self.__socket = None


class Rpc:
    def __init__(self,host='localhost', port=8080) -> None:
        self.__host = host
        self.__port = port
        self.__reslutqueue = ResultQueue()
        self.__id = 0
        self._isconnected=False
        self._buffer = b''

    async def async_connect(self):
        """连接服务端,异步方法"""
        if self._isconnected:
            return        
        self.__reader, self.__writer = await asyncio.open_connection(self.__host, self.__port)
        self._isconnected = True


    def connect(self):
        """连接服务端"""
        if self._isconnected:
            return

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((self.__host, self.__port))
        self._isconnected = True


    def gen_request(self,method_name,args,dicts)->dict:
        """生成请求"""
        self.__id += 1
        return { 'jsonrpc':'2.0', 'id': self.__id, 'method':method_name, 'args':args, 'dicts':dicts }


    async def async_call(self,method_name,*args,**dicts):
        """异步rpc调用"""
        # asyncio.create_task()        
        request:dict = self.gen_request(method_name,args,dicts)
        self.__writer.write(json.dumps(request).encode('utf-8'))
        await self.__writer.drain()
        while True:
            data = await self.__reader.read(204800)
            response:dict = json.loads(data.decode('utf-8').strip())
            self.__reslutqueue.push(response)
            response = self.__reslutqueue.pull(request['id'])
            if response:
                return response
            await asyncio.sleep(0)

    
    def close(self):
        if self.__socket:
            try:
                self.__socket.sendall('')  # 发送空信息，告诉服务端关闭连接                
            except:
                try:
                    self.__socket.shutdown(socket.SHUT_RDWR)  # 关闭读和写
                except OSError:
                    pass
            finally:
                self.__socket.close()
                self.__socket = None



    def call(self,method_name,*args,**dicts):
        request:dict = self.gen_request(method_name,args,dicts)
        request_packet = pack_data2_utran('jsonrpc',request)
        self.__socket.sendall(request_packet)
        try:
            while True:
                chunk = self.__socket.recv(1024)
                if not chunk:
                    raise ConnectionError('Connection closed by server')
                name,message, self._buffer = unpack_data2_utran(chunk, self._buffer)
                
                if message is not None:
                    response:dict = json.loads(message.decode('utf-8').strip())
                    self.__reslutqueue.push(response)
                    
                response = self.__reslutqueue.pull(request['id'])
                if response:
                    return response
                
        except Exception as e:
            self.close()
            raise e
    

    async def __loop(self):
        while self.__hoding:
            data = await self.__reader.read(204800)            
            response:dict = json.loads(data.decode('utf-8').strip())
            self.__reslutqueue.push(response)
            

    async def close(self):
        self.__writer.write('')
        await self.__writer.drain()
        self.__hoding = False
        self.__writer.close()


    def __enter__(self):
        asyncio.run(self.run())
        return self


    async def __aenter__(self):
        asyncio.run(self.run())
        return self
        
    async def __aexit__ (self):
        self.close()
        return True



if __name__ == '__main__':
    rpc = Rpc()
    rpc.connect()
    res = rpc.call('add',a=1,b=2)
    print(res)

    res = rpc.call('add2',dict(a=7,b=2))
    print(res)

    res = rpc.call('add3',[8,7])
    print(res)

    res = rpc.call('add100',[8,7])
    print(res)

    # async def main():
    #     rpc = Rpc()
    #     loop = await rpc.run()

    #     # rpc.call('add',a=1,b=2)
    #     # print(res)
    #     # asyncio.gather()

    #     res2 = await rpc.call('add',a=8,b=2)
    #     print(res2)

    #     # return loop()

    # asyncio.run(main())