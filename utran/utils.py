
import asyncio
import inspect
import re
import ujson
from typing import Union


def unpack_data2_utran(data:bytes, buffer:bytes=b'',maxsize:int=102400)->tuple[Union[bytes,None],Union[bytes,None],bytes]:
    """
    根据utran协议从接收到的字节流中解析出完整的消息
    Args:
        data: 接收到的字节流
        buffer: 缓冲区中未处理完的数据
        maxsize: 支持数据的最大长度

    Returns: 
        如果解析成功完整消息，则返回请求类型的名称，消息和剩余字节流；否则返回None和原始字节流

    Utran协议:
        ```
        rpc/subscribe/unsubscribe/publish
        length:xx
        encrypt:0/1
        message_json
        ```
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
    
    
    # 解析是否加密
    encrypt_start = length_end + 1
    encrypt_end = buffer.find(b'\n', encrypt_start)
    
    if encrypt_end == -1:
        return None, None, buffer
    
    encrypt_str = buffer[encrypt_start:encrypt_end]
    
    if not encrypt_str.startswith(b'encrypt:'):
        raise Exception('Error: Invalid message format. Missing "encrypt" keyword in third line.')

    try:
        encrypt = int(encrypt_str.split(b':')[1])
    except:
        raise Exception('Error: Value error. "encrypt" value error in third line.')


    # 解析数据内容
    data_start = encrypt_end + 1
    data_end = data_start + message_length
    
    if len(buffer) < data_end:
        return None, None, buffer
    
    name = buffer[:name_end]
    message_data = buffer[data_start:data_end]        
    remaining_data = buffer[data_end:]
    
    if encrypt:
        # 加密算法还未实现
        pass

    return name, message_data, remaining_data
    

def pack_data2_utran(name:str,message:dict,encrypt:bool=False)->bytes:
    """
    根据utran协议将要发送的消息打包成二进制格式

    Utran协议:
        ```
        rpc/subscribe/unsubscribe/publish
        length:xx
        encrypt:0/1
        message_json
        ```

    Args:
        name: 请求类型的名称
        message: 要发送的消息（dict类型）
        encrypt: 是否加密数据

    Returns:
        打包后的二进制数据
    """
    message_json = ujson.dumps(message).encode('utf-8')
    
    if encrypt:
        # 加密算法还未实现
        pass
            
    message_length = len(message_json)
    
    # 打包数据
    data = b''
    data += name.encode('utf-8') + b'\n'
    data += f'length:{message_length}\n'.encode('utf-8')
    data += f'encrypt:{int(encrypt)}\n'.encode('utf-8')
    data += message_json
    
    return data



def parse_utran_uri(uri:str)->tuple[str, int]:
    """#解析uri
    Returns:
        返回host和port
    """
    result = re.search(r"//([^:/]+):(\d+)", uri)
    if result:
        host = result.group(1)
        port = result.group(2)
        return host, port
    else:
        raise ValueError(f'Uri error:{uri}')
    


def parameter_convert_list(fun,*args,**kwds):
    """函数或方法的参数，转成纯列表参数"""
    return [v for k,v in parameter_serialization(fun,*args,**kwds)]


def parameter_convert_dict(fun,*args,**kwds):
    """函数或方法的参数，转成纯字典参数"""
    return dict(parameter_serialization(fun,*args,**kwds))


def parameter_serialization(fun,*args,**kwds):
    """函数或方法的参数序列化"""
    params:tuple = tuple(inspect.signature(fun).parameters.keys())
    default_values:tuple= tuple([i.default for i in tuple(inspect.signature(fun).parameters.values()) if i.default is not inspect._empty])
    sp = inspect.getfullargspec(fun)
    varargs:str = sp.varargs
    varkw:str = sp.varkw
    args = list(args)

    _params:list = list(params)
    if varargs in params: _params.remove(varargs)
    if varkw in params: _params.remove(varkw)
    _default:dict = dict(zip(_params[len(default_values)+1:],default_values))


    s = len(default_values)
    if default_values:
        if varkw:
            s+=1
        params_ = params[:s+1]        
    else:
        params_ = params
  
    
    res_ = []    
    for i in range(len(params_)):
        n = params_[i]
        if n==varargs:
            res_.append((n,args[i:]))
            break
        if i<len(args):
            res_.append((n,args[i]))
        else:
            if n in kwds:
                res_.append((n,kwds.pop(n)))
            else:
                raise TypeError(f'{fun.__name__}() missing 1 required positional argument: "{n}"')

    _res = []
    for n in params[-s:]:
        if n == varkw:
            _res.append((n,kwds))
            kwds = None
            break
        if n in kwds:
            _res.append((n,kwds.pop(n)))
        elif _default:
            _res.append((n,_default.get(n)))
    
    if kwds:
        # 关键字参数过多
        keys = ",".join(kwds.keys())
        raise TypeError(f'{fun.__name__}() got an unexpected keyword argument "{keys}".')

    res = res_+_res
    if len(params)!=len(res):
        # 参数数量不正确
        raise TypeError(f'{fun.__name__}() The number of parameters is incorrect.')

    return res_+_res