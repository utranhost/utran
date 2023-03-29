
import inspect
from dataclasses import dataclass
from functools import partial

from utran.object import BaseDataModel, UtState


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


@dataclass
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
    name:str
    methodType:str
    callable:callable
    checkParams:bool
    checkReturn:bool
  
    def __post_init__(self) -> None:
        """"""
        self.cls: str = ''
        if inspect.ismethod(self.callable):
            self.cls = self.callable.__self__.__class__.__name__

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


    async def execute(self,args:tuple,dicts:dict)->tuple[UtState,any,str]:
        """ 执行注册的函数或方法
        Returns:
            返回值：状态，结果，错误信息
        """
        result = None
        state = UtState.SUCCESS
        error = ''
        if self.checkParams:
            try:
                args,dicts = cheekType(self.params,self.annotations,args,dicts)
            except Exception as e:
                state = UtState.FAILED
                error = str(e)
                return state,result,error
        try:
            if self.asyncfunc:
                res = await self.callable(*args,**dicts)
            else:
                res = self.callable(*args,**dicts)
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

    注:只有注册函数或方法指定了类型时以上参数才会起作用
    """
    def __init__(self,checkParams:bool=True,checkReturn:bool=True) -> None:
        self.__rpc_methods = dict()     # {method_name:{callable:callable,}}
        self.__get_methods = dict()     # {path:{callable:callable,info:{}}}
        self.__post_methods = dict()    # {path:{callable:callable,info:{}}}
        self.__checkParams = checkParams
        self.__checkReturn = checkReturn

    @property
    def methods_of_get(self):
        return self.__get_methods
    
    @property
    def methods_of_post(self):
        return self.__post_methods

    @property
    def methods_of_rpc(self):
        return self.__rpc_methods
    

    def rpc(self,_f_=None,_n_=None,**opts):
        """# RPC注册
        支持：类/类方法/类实例/函数的注册

        Args:
            第一个参数 (非固定): 1.装饰器用法时，为注册的名称；2.方法调用时，为类/类方法/类实例/函数
            第二个参数 (非固定): 注册的名称，只有在方法调用时才有二个参数
            **opts (可选): 该项只有在给类加装饰器时，用来指定类实例化的参数

        支持装饰器用法 @register.rpc
        """  
        return self._register(_f_,_n_,'rpc',**opts)

    def get(self,_f_=None,_n_=None,**opts):
        """# GET注册

        ## 支持装饰器用法:
        > @register.get("/home")

        ## 无参数使用:
        > @register.get
        > 会将函数名或方法名作为路径使用
        
        """  
        return self._register(_f_,_n_,'get',**opts)

    def post(self,_f_=None,_n_=None,**opts):      
        """# POST注册
        > 使用方法：见GET方法
        """   
        return self._register(_f_,_n_,'post',**opts)


    def _update(self,methodType:str,func:callable,name:str):
        """更新注册表"""
        if methodType=='rpc':
            if not name[0].isalpha():
                raise ValueError(f"'{name}' cannot be used as a func'name,must be startwith a letter")
            self.__rpc_methods[name] = RMethod(name,'RPC',func,self.__checkParams,self.__checkReturn)
            return

        if methodType=='get':
            name = name.replace('.','/')
            if not name.startswith('/'):
                name='/'+name                
            self.__get_methods[name] = RMethod(name,'GET',func,self.__checkParams,self.__checkReturn)
            return

        if methodType=='post':
            name = name.replace('.','/')
            if not name.startswith('/'):
                name='/'+name
            self.__post_methods[name] = RMethod(name,'POST',func,self.__checkParams,self.__checkReturn)
            return


    def _register(self,_f_=None,_n_=None,_t_:str=None,**opts):
        """通用注册，支持注册函数，类（自动实例化），类实例，"""
        if _f_ is None:
            return partial(self._register, _n_=_n_,_t_=_t_,**opts)
        
        if type(_f_)==str:
            _n_ = _f_.strip()
            # if _n_ and _n_[0].isalpha():
            if _n_:
                return partial(self._register,_n_=_n_,_t_=_t_,**opts)
            else:
                raise ValueError(f"'{_f_}' cannot be used as a registered name!")
            
        if inspect.isfunction(_f_) or inspect.ismethod(_f_):
            if not _n_:
                _n_ = _f_.__name__            
            self._update(_t_,_f_,_n_)
        elif inspect.ismodule(_f_):
            raise ValueError(f"'{_f_.__name__} 'module could not be registered!")
        else:            
            if not _n_:
                raise ValueError(f"The name is required!")
            if type(_n_)!=str:
                raise ValueError(f"The name '{_n_}' is not a string!")
            
            if inspect.isclass(_f_):
                _instance = _f_(**opts)
            else:
                _instance = _f_

            for i in dir(_instance):
                if i.startswith("_"):
                    continue
                _f = getattr(_instance,i)
                if inspect.ismethod(_f) or inspect.isfunction(_f):
                    method_name = f'{_n_}.{i}'
                    self._update(_t_,_f,method_name)
        return _f_