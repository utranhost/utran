import inspect



def to(fun,*args,**kwds):
    """函数或方法的参数，转成纯字典参数，或纯列表参数"""
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
    


def test(a,b,c,*ages,name='iklae',age=18,**kwds):
    print(a,b,c,name,age)

def test2(a,b,c):
    print(a,b,c)
print(to(test2,1,2,5,c=3))


print(to(test,*[1,2,3,1,5],**dict(age=16,pic=789)))
# print(dict(to(test,*[],**dict(b=2,c=3,age=16,pic=789))))


# import os
# os.sys.path.append(os.path.abspath('./'))
# os.sys.path.append(os.path.abspath('../'))



# from utran.register import RMethod


# RMethod('test','post',test,True,True,None)


