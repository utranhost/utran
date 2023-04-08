
import asyncio
import inspect
from functools import partial
from concurrent.futures import ProcessPoolExecutor
from typing import Callable

from utran.object import BaseDataModel, UtState
from utran.log import logger

def allowType(v,t,n):
    """ 
    # 类型转换
    ### 1.当自身的数据类型与指定的数据一致时，直接返回该数据；
    ### 2.当自身的数据类型与指定的数据不一致，首先尝试是否可以之间转换为该类型，否则，检查是否为允许类型，如果是则转换为该类型的数据，否则报错TypeError。

    Args:
        v: 数据
        t (str): 数据类型
        n (str): 可调用对象的名称
    """
    if type(v)==t:
        return v
    else:
        try:
            v =  t(v)
            return v
        except TypeError:
            pass

        class_ = t
        if class_ and issubclass(class_,BaseDataModel):
            try:
                return class_(**v)
            except Exception as e:
                raise TypeError('Error converting data:',e)
        else:
            raise TypeError(f"Type error, value '{n}' must be {t} type.")


def cheekType(params:tuple,annotations:dict,args:tuple,dicts:dict={})->tuple:
    """
    # 检查类型
    当指定的类型属于BaseDataModel的子类时，将尝试进行自动转换
    """
    args = list(args)   
    
    for i in range(len(params)):
        n = params[i]
        t = annotations.get(n)
        if not t:
            continue
        try:
            v = args[i]
            args[i] = allowType(v,t,n)
        except IndexError:
            try:
                v = dicts[n]
                dicts[n] = allowType(v,t,n)
            except KeyError:
                continue
    return tuple(args),dicts



def asyncfn_runner(fn:Callable,*args,**kwds):
    """子进程中的异步执行器"""
    return asyncio.run(fn(*args,**kwds))

class RMethod:
    """
    #存放注册方法的数据类
    Attributes:
        name (str): 名称或路径
        methodType (str): 类型 GET / POST / RPC
        callable (callable): 可调用的方法/函数
        checkParams (bool): 是否检查参数
        checkReturn (bool): 是否检查返回值
        cls (str): 类名，类方法才会有
        doc (str): 描述
        params (tuple): 参数
        default_values (tuple): 参数默认值
        annotations (dict): 类型声明
        varargs (str): 参数中*args的名称
        varkw (str): 参数中**dicts的名称
        returnType (str): 返回值的类型
        asyncfunc (bool): 是否为异步函数或方法
    """
  
    __slots__ = ('name',
                 'methodType',
                 'callable',
                 'checkParams',
                 'checkReturn',
                 'cls',
                 'doc',
                 'params',
                 'default_values',
                 'annotations',
                 'varargs',
                 'varkw',
                 'returnType',
                 'asyncfunc',
                 'useProcess')

    def __init__(self,
                 name:str,
                 methodType:str,
                 callable:callable,
                 checkParams:bool,
                 checkReturn:bool,
                 useProcess:bool=False) -> None:
        """"""
        self.name = name
        self.methodType = methodType
        self.callable = callable
        self.checkParams = checkParams
        self.checkReturn = checkReturn     
        self.useProcess = useProcess
        self.cls: str = '' if not inspect.ismethod(self.callable) else self.callable.__self__.__class__.__name__
        self.params:tuple = tuple(inspect.signature(self.callable).parameters.keys())        
        self.default_values:tuple= tuple([i.default for i in tuple(inspect.signature(self.callable).parameters.values()) if i.default is not inspect._empty])
        self.doc:str = inspect.getdoc(self.callable)
        annotations = dict([(k,v.annotation) for k,v in  inspect.signature(self.callable).parameters.items() if v.annotation is not inspect._empty])
        for an in annotations.keys():
            annotations[an] = annotations[an]
        self.annotations:dict = annotations
        sp = inspect.getfullargspec(self.callable)
        self.varargs:str = sp.varargs
        self.varkw:str = sp.varkw
        self.returnType:str = sp.annotations.get('return')
        self.asyncfunc:bool = inspect.iscoroutinefunction(self.callable)


    async def execute(self,args:tuple,dicts:dict,pool:ProcessPoolExecutor=None)->tuple[UtState,any,str]:
        """ 执行注册的函数或方法
        Args:
            args: 列表参数
            dicts: 字典参数
            pool: 进程池
            
        Returns:
            返回值：状态，结果，错误信息
        """
        result = None
        state = UtState.SUCCESS
        error = ''

        # 1.检查参数
        if self.checkParams:
            try:
                args,dicts = cheekType(self.params,self.annotations,args,dicts)
            except Exception as e:
                state = UtState.FAILED
                error = str(e)
                return state,result,error
        try:
            # 2.执行注册函数
            if self.useProcess:
                # 进程中执行
                if pool is None: 
                    logger.error(f'The function "{self.name}" runs in a child process, but the server has no worker process')
                    raise RuntimeError(f'The function "{self.name}" runs in a child process, but the server has no worker process')

                if self.asyncfunc:
                    fn = partial(asyncfn_runner,self.callable,*args,**dicts)
                else:
                    fn = partial(self.callable,*args,**dicts)

                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(pool,fn)

            else:
                if self.asyncfunc:
                    # 异步执行
                    res = await self.callable(*args,**dicts)
                else:
                    # 正常执行
                    res = self.callable(*args,**dicts)

            # 3.检查返回值
            if self.checkReturn and self.returnType:
                try:
                    res= allowType(res,self.returnType,self.name)
                    result = res
                except:
                    state = UtState.FAILED
                    error = f"Return value error.'{type(res)}' is not of '{self.returnType}' type"
            else:                
                result = res
        except Exception as e:
            state = UtState.FAILED
            error = str(e)
        
        return state,result,error


class Register:
    """
    # 注册类，用于注册本地的可调用函数，
    支持(rpc、get、post)注册

    Args:
        checkParams (bool): 调用注册函数或方法时，是否检查参数类型，开启后当类型为数据模型时可以自动转换
        checkReturn (bool): 调用注册函数或方法时，是否检查返回值类型，开启后当类型为数据模型时可以自动转换
        pool: 进程池对象
    注:只有注册函数或方法指定了类型时以上参数才会起作用
    """
    __slots__ = ('__rpc_methods','__get_methods','__post_methods','__checkParams','__checkReturn','_temp_opts','_workers')

    def __init__(self,checkParams:bool=True,checkReturn:bool=True,workers:int=0) -> None:
        self.__rpc_methods = dict()     # {method_name:{callable:callable,}}
        self.__get_methods = dict()     # {path:{callable:callable,info:{}}}
        self.__post_methods = dict()    # {path:{callable:callable,info:{}}}
        self.__checkParams = checkParams
        self.__checkReturn = checkReturn
        self._temp_opts = dict()
        self._workers = workers

    @property
    def methods_of_get(self):
        return self.__get_methods
    
    @property
    def methods_of_post(self):
        return self.__post_methods

    @property
    def methods_of_rpc(self):
        return self.__rpc_methods
    

    def rpc(self,*fn,name=None,ins_args:tuple=tuple(),ins_kwds:dict=dict(),**opts):
        """# RPC注册
        支持：类/类方法/类实例/函数的注册

        ## 1.装饰器调用时参数解释 
          `@register.rpc(name=?,ins_kwds=?,ins_args=?,**opts)`
        Attributes:
            name (str): 被远程调用的方法名称，非`class`为可选，`class`为必填
            ins_args (tuple): 只有注册`class`时才有这个选项，为类实例化的参数
            ins_kwds (dict): 只有注册`class`时才有这个选项，为类实例化的关键字参数
            **opts: 选项。例如: useProcess = True 使用子进程执行，还有 checkParams、checkReturn等

        注: 注册非`class`或`class`实例时，可支持无参调用 `@register.rpc`
            
        ## 2.方法调用时参数解释 
        `register.rpc(fn,name=?,ins_kwds=?,ins_args=?,**opts)`
        Attributes:
            fn: 要注册的函数或方法，也可以是`class`或者`class`实例
            name (str): 被远程调用的方法名称
            ins_args (tuple): 只有注册`class`时才有这个选项，为类实例化的参数
            ins_kwds (dict): 只有注册`class`时才有这个选项，为类实例化的关键字参数
            **opts: 选项。例如: useProcess = True 使用子进程执行，还有 checkParams、checkReturn等

        """  
        fn = fn[0] if fn else None
        return self._register(fn,name,'rpc',ins_args=ins_args,ins_kwds=ins_kwds,opts=opts)



    def get(self,*fn,path:str=None,ins_args:tuple=tuple(),ins_kwds:dict=dict(),**opts):
        """# GET注册

        关于名称:
            名称必须是小写,如非小写会自动转为小写。名称前会加上`/`斜杠，转为路径

        
        支持：类/类方法/类实例/函数的注册

        ## 1.装饰器调用时参数解释 
          `@register.get(path=?,ins_kwds=?,ins_args=?,**opts)`
        Attributes:
            path (str): 注册的路径名称，非`class`为可选，`class`为必填
            ins_args (tuple): 只有注册`class`时才有这个选项，为类实例化的参数
            ins_kwds (dict): 只有注册`class`时才有这个选项，为类实例化的关键字参数
            **opts: 选项。例如: useProcess = True 使用子进程执行，还有 checkParams、checkReturn等


        注: 注册非`class`或`class`实例时，可支持无参调用 `@register.get`
            
        ## 2.方法调用时参数解释 
        `register.get(fn,path=?,ins_kwds=?,ins_args=?,**opts)`
        Attributes:
            fn: 要注册的函数或方法，也可以是`class`或者`class`实例
            path (str): 注册的路径名称
            ins_args (tuple): 只有注册`class`时才有这个选项，为类实例化的参数
            ins_kwds (dict): 只有注册`class`时才有这个选项，为类实例化的关键字参数
            **opts: 选项。例如: useProcess = True 使用子进程执行，还有 checkParams、checkReturn等

        """
        fn = fn[0] if fn else None
        return self._register(fn,path,'get',ins_args=ins_args,ins_kwds=ins_kwds,opts=opts)



    def post(self,*fn,path:str=None,ins_args:tuple=tuple(),ins_kwds:dict=dict(),**opts):      
        """# POST注册
        关于名称:
            名称必须是小写,如非小写会自动转为小写。名称前会加上`/`斜杠，转为路径

        支持：类/类方法/类实例/函数的注册

        ## 1.装饰器调用时参数解释 
          `@register.post(path=?,ins_kwds=?,ins_args=?,**opts)`
        Attributes:
            path (str): 注册的路径名称，非`class`为可选，`class`为必填
            ins_args (tuple): 只有注册`class`时才有这个选项，为类实例化的参数
            ins_kwds (dict): 只有注册`class`时才有这个选项，为类实例化的关键字参数
            **opts: 选项。例如: useProcess = True 使用子进程执行，还有 checkParams、checkReturn等

        注: 注册非`class`或`class`实例时，可支持无参调用 `@register.post`
            
        ## 2.方法调用时参数解释 
        `register.post(fn,path=?,ins_kwds=?,ins_args=?,**opts)`
        Attributes:
            fn: 要注册的函数或方法，也可以是`class`或者`class`实例
            path (str): 注册的路径名称
            ins_args (tuple): 只有注册`class`时才有这个选项，为类实例化的参数
            ins_kwds (dict): 只有注册`class`时才有这个选项，为类实例化的关键字参数
            **opts: 选项。例如: useProcess = True 使用子进程执行，还有 checkParams、checkReturn等

        """ 
        fn = fn[0] if fn else None
        return self._register(fn,path,'post',ins_args=ins_args,ins_kwds=ins_kwds,opts=opts)


    def creatRMethod(self,**opts):
        """# 创建RMethod实例，并保存到对应容器中。
        ## opts参数字段
        Attributes:
            name (str): 注册的名称或路径
            methodType (str): 注册类型 GET / POST / RPC
            callable (callable): 可调用的方法/函数
            checkParams? (bool): 可选，是否检查参数
            checkReturn? (bool): 可选，是否检查返回值
            useProcess? (bool):  可选，是否使用子进程执行
        """
        name:str = opts.get('name')
        methodType:str = opts.get('methodType')

        opts['useProcess'] = False if opts.get('useProcess') == None else opts.get('useProcess')
        opts['checkParams'] = self.__checkParams if opts.get('checkParams') == None else opts.get('checkParams')
        opts['checkReturn'] = self.__checkReturn if opts.get('checkReturn') == None else opts.get('checkReturn')

        if methodType=='rpc':
            name = opts.get('name')
            if not name[0].isalpha():
                raise ValueError(f"Registration error,The name '{name}' must start with a letter")
            self.__rpc_methods[name] = RMethod(**opts)
            return

        if methodType=='get':
            name = name.replace('.','/')
            if not name.startswith('/'):
                name='/'+name
            name_ = name.lower()
            if name != name_:
                logger.warning(f'PathName changed,The path "{name}" changes to "{name_}"')
            self.__get_methods[name_] = RMethod(**opts)
            return

        if methodType=='post':
            name = name.replace('.','/')
            if not name.startswith('/'):
                name='/'+name
            name_ = name.lower()
            if name != name_:
                logger.warning(f'PathName changed,The path "{name}" changes to "{name_}"')            
            self.__post_methods[name_] = RMethod(**opts)
            return


    def _register(self,_f_=None,_n_=None,_t_:str=None,ins_args:tuple=tuple(),ins_kwds:dict=dict(),opts:dict=dict()):
        """通用注册，支持注册函数，类（自动实例化），类实例，"""
        if _f_ is None:
            return partial(self._register, _n_=_n_,_t_=_t_,ins_args=ins_args,ins_kwds=ins_kwds,opts=opts)
        
        if type(_f_)==str:
            _n_ = _f_.strip()
            # if _n_ and _n_[0].isalpha():
            if _n_:
                return partial(self._register,_n_=_n_,_t_=_t_,ins_args=ins_args,ins_kwds=ins_kwds,opts=opts)
            else:
                raise ValueError(f"Registration error,'{_f_}' cannot be used as a registered name!")
            
        if inspect.isfunction(_f_) or inspect.ismethod(_f_):
            if not _n_:
                _n_ = _f_.__name__
            
            opts_:dict = dict(name=_n_,methodType=_t_,callable=_f_)
            opts_.update(opts)
            self.creatRMethod(**opts_)
        elif inspect.ismodule(_f_):
            raise ValueError(f"Registration error,module '{_f_.__name__}' could not be registered!")
        else:
            # 注册class
            if not _n_:
                if inspect.isclass(_f_):
                    raise ValueError(f"Registration error,The '{_f_.__name__}' class is not named!")
                else:
                    
                    raise ValueError(f"Registration error,The '{type(_f_).__name__}' instance is not named!")
                
            if type(_n_)!=str:
                raise ValueError(f"Registration error,The name '{_n_}' is not a string!")
            
            if inspect.isclass(_f_):
                _instance = _f_(*ins_args,**ins_kwds)
            else:
                _instance = _f_


            for i in dir(_instance):
                if i.startswith("_"):
                    continue
                _f = getattr(_instance,i)
                if inspect.ismethod(_f) or inspect.isfunction(_f):
                    method_name = f'{_n_}.{i}'
                    opts_:dict = dict(name=method_name,methodType=_t_,callable=_f)
                    opts_.update(opts)
                    self.creatRMethod(**opts_)
                    
        return _f_