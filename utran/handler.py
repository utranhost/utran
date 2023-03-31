# 处理请求


import asyncio
from utran.object import PubRequest, RpcRequest, SubRequest, UnSubRequest, UtType, UtResponse, UtState
from utran.register import RMethod, Register
from utran.utils import ClientConnection, SubscriptionContainer


async def process_request(request:dict,connection:ClientConnection,register:Register,sub_container:SubscriptionContainer)->bool:
    """# 处理请求总入口
    Args:
        request (dict): 请求体
        connection (ClientConnection): 客户端连接
        register (Register): 注册类实例
        sub_container (SubscriptionContainer): 存放订阅者的容器实例

    Returns:
        返回一个布尔值,是否结束连接
    """
    requestType = request.get('requestType')
    id = request.get("id")
    
    if UtType.RPC.value==requestType:
        #  Rpc请求
        methodName = request.get("methodName")
        args = request.get("args") or tuple()
        dicts = request.get("dicts") or dict()
        return await process_rpc_request(RpcRequest(id=id,methodName=methodName,args=args,dicts=dicts),connection,register)

    elif UtType.UNSUBSCRIBE.value==requestType:
        # 取消订阅 topic        
        topics = request.get("topics")
        return await process_unsubscribe_request(UnSubRequest(id=id,topics=topics),connection,sub_container)

    elif UtType.SUBSCRIBE.value==requestType:
        # 订阅 topic
        topics = request.get("topics")
        return await process_subscribe_request(SubRequest(id=id,topics=topics),connection,sub_container)

    elif UtType.PUBLISH.value==requestType:
        topic = request.get("topic")
        msg = request.get("msg")
        return await process_publish_request(PubRequest(id=id,topic=topic,msg=msg),sub_container)

    else:
        # logging.log(f"处理请求时,出现不受支持的请求,请求的内容：{request}")
        return True


async def process_rpc_request(request:RpcRequest,connection:ClientConnection,register:Register)->bool:
    """
    # 处理rpc请求
    Args:
        request (dict): 请求体
        connection (ClientConnection): 客户端连接
        register (Register): 存放订阅者的容器实例

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
    
    await connection.send(response)
    return False


async def process_subscribe_request(request:SubRequest,connection:ClientConnection,sub_container:SubscriptionContainer)->bool:
    """
    # 处理subscribe订阅请求
    Args:
        request (SubRequest): 请求体            
        connection (ClientConnection): 客户端连接
        sub_container (SubscriptionContainer): 存放订阅者的容器实例

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

    if not topics:
        response.state = UtState.FAILED
        response.result = dict(allTopics=connection.topics,subTopics=[])
        response.error = '没有指定topics'
        await connection.send(response)
    else:
        if not sub_container.has_sub(connection.id):
            t_ = sub_container.add_sub(connection,topics)
            response.result = dict(allTopics=connection.topics,subTopics=t_)
        else:
            t_ = sub_container.add_topic(connection.id,topics)
            response.result = dict(allTopics=connection.topics,subTopics=t_)
        await connection.send(response)

    return False
    

async def process_unsubscribe_request(request:UnSubRequest,connection:ClientConnection,sub_container:SubscriptionContainer)->bool:
    """
    # 处理unsubscribe取消订阅请求
    Args:
        uid (str): 主体的uid
        request (dict): 请求体            
        hoding (bool): 是否处于订阅状态中
    
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

    if sub_container.has_sub(connection.id):
        t_ = sub_container.remove_topic(connection.id,topics)
        response.result = dict(unSubTopics=t_,allTopics=connection.topics)
        await connection.send(response)
        return False
    else:
        response.state = UtState.FAILED
        response.error = '非订阅者，无法执行该操作，服务器将关闭连接！'
        await connection.send(response)
        return True


async def process_publish_request(request:PubRequest,sub_container:SubscriptionContainer)->bool:
    """
    # 处理publish发布请求
    Args:
        uid (str): 主体的uid
        request (dict): 请求体
        
    ## request 请求体格式↓
    Attributes:
        publish (str): 用于声明请求的类型，版本号1.0
        topic (str): topic名称
        msg (dict): 发布的消息

    Returns:
        返回一个布尔值,是否结束连接
    """
    topic:str = request.topic
    msg:dict = request.msg
    response =UtResponse(id=request.id,responseType=request.requestType,state=UtState.SUCCESS)

    # asyncio.sleep(0) 释放控制权，用于防止publish被持续不间断调用而导致的阻塞问题
    if not request.topic:
        response.state = UtState.FAILED
        response.error = '推送了一个空topic，服务器将关闭连接！'
        return True
    
    subIds:list = sub_container.get_subId_by_topic(topic)
    for subid in subIds:
        sub:ClientConnection = sub_container.get_sub_by_id(subid)
        response.result = msg
        if sub:await sub.send(response)
        
    await asyncio.sleep(0)
    return False




