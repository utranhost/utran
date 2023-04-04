import asyncio
# from utran.client.baseclient import BaseClient


class RPCProxy:
    def __init__(self):
        self._opts = dict()
        # self._bsclient = BaseClient()

    def __getattr__(self, name):
        def wrapper(*args, **dicts):
            print(name,args,dicts)
            return 123
            # loop = asyncio.get_event_loop()
            # result = loop.run_until_complete(self._bsclient.call(name,args=args,dicts=dicts,**self._opts))            
            # return result
        return wrapper

    def option(self,**opts):
        self._opts = opts
        return self
    

print(RPCProxy().option(name=12).my(12,14))