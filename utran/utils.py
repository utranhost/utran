
import asyncio
import inspect
import re
import ujson
from typing import Callable, Coroutine, Union


def unpack_data2_utran(buffer:bytes=b'')->tuple[str,dict,int,bytes]:
    """
    根据utran协议从接收到的字节流中解析出完整的消息
    Args:
        buffer: 字节数据

    Returns: 
        msgType (str):消息类型
        header (dict):头部
        residual_datasize (int):未读取字节数
        msg:剩余字节

    Utran协议:
        ```
        rpc/subscribe/unsubscribe/publish/multicall
        length:xx
        encrypt:0/1
        message_json
        ```
    """
    if b'length' not in buffer or b'id' not in buffer:
        raise ValueError('The utran protocol is invalid')

    try:
        head,msg = buffer.split(b'\r\n')
        head = head.split(b'\n')[:-1]
        msgType,header = (head[0],head[1:])
    except:
        raise ValueError('The utran protocol is invalid')
    
    if msgType not in [b'rpc',b'subscribe',b'unsubscribe',b'publish',b'multicall']:
        raise ValueError('The utran protocol is invalid')
    
    try:
        msgType = msgType.decode('utf-8')
        header = dict([i.decode('utf-8').split(':') for i in header])
        header['encrypt'] = bool(int(header.get('encrypt')))
        header['length'] = int(header.get('length'))
        header['id'] = int(header.get('id'))        
    except:
        raise ValueError('The utran protocol is invalid')
    
    residual_datasize = header['length'] - len(msg)
       
    return msgType,header,residual_datasize,msg
    


def pack_data2_utran(id:int,name:str,message:Union[dict,bytes],encrypt:bool=False)->bytes:
    """
    根据utran协议将要发送的消息打包成二进制格式

    Utran协议:
        ```
        rpc/subscribe/unsubscribe/publish
        length:xx
        encrypt:0/1
        id:1
        
        message_json
        ```

    Args:
        id: 整数类型的值
        name: 请求类型的名称
        message: 要发送的消息（dict类型） 或者 bytes
        encrypt: 是否加密数据

    Returns:
        打包后的二进制数据
    """
    if type(message) == dict:
        message_json = ujson.dumps(message).encode('utf-8')
    elif type(message) != bytes:
        raise ValueError('Packaging error,The message must be a dict or bytes ')

    if encrypt:
        # 加密算法还未实现
        pass
            
    message_length = len(message_json)
    
    # 打包数据
    data = b''
    data += name.encode('utf-8') + b'\n'
    data += f'length:{message_length}\n'.encode('utf-8')
    data += f'encrypt:{int(encrypt)}\n'.encode('utf-8')
    data += f'id:{id}\n'.encode('utf-8')
    data += b'\r\n'
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


def asyncfn_runner(fn:Union[Callable,Coroutine],*args,**kwds):
    """子进程或线程中的异步执行器"""
    if asyncio.iscoroutinefunction(fn):
        return asyncio.run(fn(*args,**kwds))
    elif asyncio.iscoroutine(fn):
        return asyncio.run(fn)
    

    