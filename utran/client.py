import asyncio
import json
import socket
import zlib


class ResultQueue:
    _resluts = dict() # {id:res,id2:res}

    def push(self,response:dict):
        """推入数据"""
        id = response.get('id')
        if id:
            self._resluts[id] = response
            return True
        else:
            return False
        

    def pull(self,id:int):
        """拉取数据，并删除"""        
        if id in self._resluts:
            return self._resluts.pop(id)
        else:
            # asyncio.sleep(0)
            return
        
def unpack_data(data:bytes, buffer:bytes=b'',maxsize:int=102400)->tuple:
    """
    从接收到的字节流中解析出完整的消息
    :param data: 接收到的字节流
    :param buffer: 缓冲区中未处理完的数据
    :param maxsize: 支持数据的最大长度
    :return: 如果解析成功完整消息，则返回请求类型的名称，消息和剩余字节流；否则返回None和原始字节流
    """
    buffer += data
    
    if len(buffer) < 4:
        return None, None, buffer
    
    # 解析名称
    name_end = buffer.find(b'\n')
    if name_end == -1:
        return None, None, buffer
    
    
    # 解析length
    length_start = name_end + 1
    length_end = buffer.find(b'\n', length_start)
    
    if length_end == -1:
        return None, None, buffer      

    length_str = buffer[length_start:length_end]
    
    if not length_str.startswith(b'length:'):
        raise Exception('Error: Invalid message format. Missing "length" keyword in second line.')
    
    try:
        message_length = int(length_str.split(b':')[1])
    except:
        raise Exception('Error: Value error. "length" value error in second line.')
    
    if message_length > maxsize:
        raise Exception('Message too long')
    
    
    # 解析compress
    compress_start = length_end + 1
    compress_end = buffer.find(b'\n', compress_start)
    
    if compress_end == -1:
        return None, None, buffer
    
    compress_str = buffer[compress_start:compress_end]
    
    if not compress_str.startswith(b'compress:'):
        raise Exception('Error: Invalid message format. Missing "compress" keyword in third line.')

    try:
        compress = int(compress_str.split(b':')[1])
    except:
        raise Exception('Error: Value error. "compress" value error in third line.')


    # 解析数据内容
    data_start = compress_end + 1
    data_end = data_start + message_length
    
    if len(buffer) < data_end:
        return None, None, buffer
    
    name = buffer[:name_end]
    message_data = buffer[data_start:data_end]        
    remaining_data = buffer[data_end:]
    
    if compress:
        message_data = zlib.decompress(message_data)

    return name, message_data, remaining_data
    

    



def pack_data(name:str, message:dict, compress=False):
    """
    将要发送的消息打包成二进制格式
    :param name: 请求类型的名称
    :param message: 要发送的消息（dict类型）
    :param compress: 是否压缩数据
    :return: 打包后的二进制数据
    """
    
    message_json = json.dumps(message).encode('utf-8')
    
    if compress:
        message_json = zlib.compress(message_json)
            
    message_length = len(message_json)
    
    # 打包数据
    data = b''
    data += name.encode('utf-8') + b'\n'
    data += f'length:{message_length}\n'.encode('utf-8')
    data += f'compress:{int(compress)}\n'.encode('utf-8')
    data += message_json
    
    return data



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
        request_packet = pack_data('jsonrpc',request)
        self.__socket.sendall(request_packet)
        try:
            while True:
                chunk = self.__socket.recv(1024)
                if not chunk:
                    raise ConnectionError('Connection closed by server')
                name,message, self._buffer = unpack_data(chunk, self._buffer)
                
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