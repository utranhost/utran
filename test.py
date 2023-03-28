import asyncio
import json
from typing import Tuple
import zlib






async def unpack_data(data:bytes, buffer:bytes=b'',maxsize:int=102400)->Tuple[Tuple[bytes,bytes] or None, bytes]:
    """
    从接收到的字节流中解析出完整的消息
    :param data: 接收到的字节流
    :param buffer: 缓冲区中未处理完的数据
    :return: 如果解析成功完整消息，则返回消息和剩余字节流；否则返回None和原始字节流
    """
    buffer += data
    
    if len(buffer) < 4:
        return None, buffer
    
    # 解析名称
    name_end = buffer.find(b'\n')
    if name_end == -1:
        return None, buffer
    
    
    # 解析length
    length_start = name_end + 1
    length_end = buffer.find(b'\n', length_start)
    
    if length_end == -1:
        return None, buffer      

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
        return None, buffer
    
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
        return None, buffer
    
    name = buffer[:name_end]
    message_data = buffer[data_start:data_end]        
    remaining_data = buffer[data_end:]
    
    if compress:
        message_data = zlib.decompress(message_data)

    return (name, message_data), remaining_data
    

    



def pack_data(name:str, message:dict, compress=False):
    """
    将要发送的消息打包成二进制格式
    :param name: 消息名称
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

async def handle_client(reader, writer):
    buffer = b''
    
    while True:
        data = await reader.read(1024)
        
        if not data:
            break
        
        message, buffer = await unpack_data(data, buffer)
        
        if message is None:
            continue
        
        # 处理消息
        response = process_message(message)
        
        # 发送响应
        writer.write(pack_data(response))
        
        await writer.drain()
    
    writer.close()

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)
    
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
