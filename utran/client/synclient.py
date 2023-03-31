import socket
import ujson
from utran.client.baseclient import BaseClient
from utran.client.que import ResultQueue
from utran.object import UtResponse, UtType
from utran.utils import gen_utran_request, unpack_data2_utran



class SyncClient(BaseClient):
    """# 同步客户端
    
    """
    __slots__=('__socket')

    def __init__(self, uri: str, reslutqueue: ResultQueue = None, encrypt: bool = False) -> None:
        super().__init__(uri, reslutqueue, encrypt)
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        """连接服务端"""
        if self._isconnected:return        
        self.__socket.connect((self._serveHost, self._servePort))
        self._isconnected = True
        

    def call(self,methodName,*args,**dicts):
        """远程调用"""
        requestId,request_packet = gen_utran_request(UtType.RPC.value,self._encrypt,methodName=methodName,args=args,dicts=dicts)
        self.__socket.sendall(request_packet)
        try:
            while True:
                chunk = self.__socket.recv(1024)
                if not chunk:
                    raise ConnectionError('Connection closed by server')
                name,message,self._buffer = unpack_data2_utran(chunk, self._buffer)
                if message is not None:
                    response:UtResponse = UtResponse(**ujson.loads(message.decode('utf-8').strip()))
                    self._reslutqueue.push(response)
                    
                response = self._reslutqueue.pull(requestId)
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