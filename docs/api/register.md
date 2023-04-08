# 注册类


```python title='注册示例'
import utran
from utran.server import Server

server = Server()

# 1.普通注册用法
server.register.rpc(add,name='puls')

# 2.类的注册,名称或路径必填
@server.register.get(path='/mycalc',ins_args=(1,2))
@server.register.rpc(name='mycalc')
class MyCalc:
    def __init__(self,a,b):
        self.a=a
        self.b=b

    def add(self,a:float,b:float):
        return a+b

    def sub(self,a:float,b:float):
        return a-b

# 3.类的实例注册
mycalc = MyCalc(2,3)
server.register.rpc(mycalc,name='mycalc2')

# 4.实例方法注册
server.register.rpc(mycalc.add,name='mycalc_add')

# 5.装饰器用法
@server.register.rpc(useProcess=True)       # 添加选项，在子进程中执行
@server.register.post(useProcess=True)
@server.register.get(useProcess=True)
@server.register.rpc(name='calc_puls')      # 指定注册的名称和路径
@server.register.post(path='/calc_puls')
@server.register.get(path='/calc_puls')
@server.register.rpc()                      # 函数式无参，使用函数名称进行注册
@server.register.post()
@server.register.get()
@server.register.rpc                        # 属性式，将使用函数名称进行注册
@server.register.post
@server.register.get
async def add(a:int,b:int):
    return a+b



utran.run(server,host='127.0.0.1',port=8081,web_port=8080)

```
::: utran.register