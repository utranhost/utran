# 处理请求


import asyncio
from typing import Union
from utran.object import UtRequest, UtType, UtResponse, UtState, create_UtRequest
from utran.register import RMethod, Register
from utran.object import ClientConnection, SubscriptionContainer


async def process_request(request:UtRequest,connection:ClientConnection,register:Register,sub_container:SubscriptionContainer)->bool:
    """# 处理请求总入口
    Args:
        request (UtRequest): 请求体
        connection (ClientConnection): 客户端连接
        register (Register): 注册类实例
        sub_container (SubscriptionContainer): 存放订阅者的容器实例

    Returns:
        返回一个布尔值,是否结束连接
    """
    
    if UtType.RPC==request.requestType:
        #  Rpc请求
        return await process_rpc_request(request,connection,register)
    
    elif UtType.UNSUBSCRIBE==request.requestType:
        # 取消订阅 topic        
        return await process_unsubscribe_request(request,connection,sub_container)

    elif UtType.SUBSCRIBE==request.requestType:
        # 订阅 topic
        return await process_subscribe_request(request,connection,sub_container)

    elif UtType.PUBLISH==request.requestType:
        # 发布        
        return await process_publish_request(request,sub_container)

    elif UtType.MULTICALL == request.requestType:
        return await process_multicall_request(request,connection,register,sub_container)

    else:
        # logging.log(f"处理请求时,出现不受支持的请求,请求的内容：{request}")
        return True


async def process_multicall_request(request:UtRequest,connection:ClientConnection,register:Register,sub_container:SubscriptionContainer)->bool:
    """处理multicall请求"""
  
    tasks = []
    for _r in request.multiple:
        r:UtRequest = create_UtRequest(_r)
        if UtType.RPC==r.requestType:
            #  Rpc请求
            tasks.append(asyncio.create_task(process_rpc_request(r,connection,register,to_send=False)))

            continue
        
        elif UtType.UNSUBSCRIBE==r.requestType:
            # 取消订阅 topic  
            tasks.append(asyncio.create_task(process_unsubscribe_request(r,connection,sub_container,to_send=False)))
            continue

        elif UtType.SUBSCRIBE==r.requestType:
            # 订阅 topic
            tasks.append(asyncio.create_task(process_subscribe_request(r,connection,sub_container,to_send=False)))
            continue

        elif UtType.PUBLISH==r.requestType:
            # 发布        
            tasks.append(asyncio.create_task(process_publish_request(r,sub_container)))
            continue

    response = UtResponse(id=request.id,
                    state=UtState.SUCCESS,
                    responseType=request.requestType)
    
    res = []
    for task in tasks:
        _response:UtResponse = await task
        res.append(_response.to_dict())

    response.result = res
    await connection.send(response)
    return False

    

async def process_rpc_request(request:UtRequest,connection:ClientConnection,register:Register,to_send:bool=True)->bool:
    """
    # 处理rpc请求
    Args:
        request (dict): 请求体
        connection (ClientConnection): 客户端连接
        register (Register): 存放订阅者的容器实例
        to_send: 是否执行发送

    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        responseType (str): 'rpc'
        state (int):  状态 0为失败，1为成功
        methodName (str): 需要执行的方法或函数名
        result (any): 执行结果
        error (str): 失败信息，订阅失败时才会有该项 

    Returns:
        返回一个布尔值,是否结束连接

    """

    method_name:str = request.methodName
    args:tuple = request.args
    dicts:dict = request.dicts
    rm:RMethod = register.methods_of_rpc.get(method_name) if method_name else None
    response = UtResponse(id=request.id,
                        state=UtState.SUCCESS,
                        methodName=method_name,
                        responseType=request.requestType)
    if rm:
        state,result,error = await rm.execute(args,dicts)
        if state == UtState.FAILED:
            response.state = UtState.FAILED
            response.error = error
        else:
            response.result = result
    else:
        response.state = UtState.FAILED
        response.error = f'The rpc server does not have "{method_name}" methods. '

    if to_send:
        await connection.send(response)
        return False
    else:
        return response




async def process_subscribe_request(request:UtRequest,connection:ClientConnection,sub_container:SubscriptionContainer,to_send:bool=True)->bool:
    """
    # 处理subscribe订阅请求
    Args:
        request (UtRequest): 请求体            
        connection (ClientConnection): 客户端连接
        sub_container (SubscriptionContainer): 存放订阅者的容器实例
        to_send: 是否执行发送

    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        responseType (str): 'subscribe'
        state (int):  订阅状态 0为失败，1为成功
        result (dict): 返回一个字典 {'subTopics':[本次成功订阅的话题],'allTopics'[该订阅者所有订阅的话题]:}
        error (str): 失败信息，订阅失败时才会有该项
        methodName (str): None

    Returns:
        返回一个布尔值,是否结束连接（该请求类型不会结束连接）

    """

    topics:list = request.topics    
    response = UtResponse(id=request.id,
                        responseType=UtType.SUBSCRIBE,
                        state=UtState.SUCCESS)
    isclose=False

    if not topics:
        response.state = UtState.FAILED
        response.result = dict(allTopics=connection.topics,subTopics=[])
        response.error = '没有指定topics'
    else:
        if not sub_container.has_sub(connection.id):
            t_ = sub_container.add_sub(connection,topics)
            response.result = dict(allTopics=connection.topics,subTopics=t_)
        else:
            t_ = sub_container.add_topic(connection.id,topics)
            response.result = dict(allTopics=connection.topics,subTopics=t_)

    if to_send:
        await connection.send(response)
        return isclose
    else:
        return response
    

async def process_unsubscribe_request(request:UtRequest,connection:ClientConnection,sub_container:SubscriptionContainer,to_send:bool=True)->bool:
    """
    # 处理unsubscribe取消订阅请求
    Args:
        request (UtRequest): 请求体            
        connection (ClientConnection): 客户端连接
        sub_container (SubscriptionContainer): 存放订阅者的容器实例
        to_send: 是否执行发送
    
    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        responseType (str): 'unsubscribe'
        state (int):  状态 0为失败，1为成功        
        result (dict): 返回一个字典 {'unSubTopics':[本次成功取消订阅的话题],'allTopics'[该订阅者所有订阅的话题]:}
        error (str): 失败信息
        methodName (str): None
        
    Returns:
        返回一个布尔值,是否结束连接
    """

    topics:list = request.topics
    response =UtResponse(id=request.id,responseType=request.requestType,state=UtState.SUCCESS)

    isclose=False

    if sub_container.has_sub(connection.id):
        t_ = sub_container.remove_topic(connection.id,topics)
        response.result = dict(unSubTopics=t_,allTopics=connection.topics)
        await connection.send(response)
    else:
        response.state = UtState.FAILED
        response.error = '非订阅者，无法执行该操作，服务器将关闭连接！'        
        isclose = True

    if to_send:
        await connection.send(response)
        return isclose
    else:
        return response



async def process_publish_request(request:UtRequest,sub_container:SubscriptionContainer)->bool:
    """
    # 处理publish发布请求
    Args:
        request: 请求体
        sub_container (SubscriptionContainer): 存放订阅者的容器实例
        
    ## response 响应体格式↓
    Attributes:
        id (int):  本次请求的id
        responseType (str): 'publish'
        state (int):  状态 0为失败，1为成功        
        result (dict): 返回一个字典 {'topic':话题,'msg':话题消息}
        error (str): 失败信息
        methodName (str): None

    Returns:
        返回一个布尔值,是否结束连接
    """
    topics:tuple[str] = request.topics
    msg:dict = request.msg
    response =UtResponse(id=request.id,responseType=request.requestType,state=UtState.SUCCESS)

    # asyncio.sleep(0) 释放控制权，用于防止publish被持续不间断调用而导致的阻塞问题
    for topic in topics:
        if not topic:
            continue
        
        subIds:list = sub_container.get_subId_by_topic(topic)
        for subid in subIds:
            sub:ClientConnection = sub_container.get_sub_by_id(subid)
            response.result = dict(topic=topic,msg=msg)
            if sub:await sub.send(response)
        
    await asyncio.sleep(0)
    return False




