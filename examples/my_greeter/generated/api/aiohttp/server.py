import aiohttp.web
import api.aiohttp.model
import asyncio
import concurrent.futures
import functools
import my_service.core.greeter.greeter
import my_service.core.greeter.model
import typing

class GreeterHandler:

    def __init__(self, impl: my_service.core.greeter.greeter.Greeter, executor: typing.Optional[concurrent.futures.Executor]=None) -> None:
        self.__impl = impl
        self.__executor = executor

    async def greet(self, raw_request: aiohttp.web.Request) -> aiohttp.web.Response:
        request = api.aiohttp.model.GreeterGreetRequest.model_validate_json(await raw_request.read())
        input_user = my_service.core.greeter.model.UserInfo(id_=request.user.id_, name=request.user.name)
        output = await asyncio.get_running_loop().run_in_executor(self.__executor, functools.partial(self.__impl.greet, user=input_user))
        response = api.aiohttp.model.GreeterGreetResponse(payload=output)
        return aiohttp.web.json_response(data=response.model_dump(mode='json', by_alias=True, exclude_none=True))

    async def notify_greeted(self, raw_request: aiohttp.web.Request) -> aiohttp.web.Response:
        request = api.aiohttp.model.GreeterNotifyGreetedRequest.model_validate_json(await raw_request.read())
        input_user = my_service.core.greeter.model.UserInfo(id_=request.user.id_, name=request.user.name)
        input_message = request.message
        await asyncio.get_running_loop().run_in_executor(self.__executor, functools.partial(self.__impl.notify_greeted, user=input_user, message=input_message))
        return aiohttp.web.json_response()

    async def stream_greetings(self, raw_request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
        websocket = aiohttp.web.WebSocketResponse()

        async def receive_inputs() -> typing.AsyncIterator[my_service.core.greeter.model.UserInfo]:
            async for msg in websocket:
                request = api.aiohttp.model.GreeterStreamGreetingsRequest.model_validate_json(msg.data)
                yield my_service.core.greeter.model.UserInfo(id_=request.users.id_, name=request.users.name)
        await websocket.prepare(raw_request)
        async for output in self.__impl.stream_greetings(receive_inputs()):
            response = api.aiohttp.model.GreeterStreamGreetingsResponse(payload=output)
            await websocket.send_str(response.model_dump_json(by_alias=True, exclude_none=True))
        return websocket

def add_greeter_subapp(app: aiohttp.web.Application, handler: GreeterHandler) -> None:
    sub = aiohttp.web.Application()
    sub.router.add_post(path='/greet', handler=handler.greet)
    sub.router.add_post(path='/notify_greeted', handler=handler.notify_greeted)
    sub.router.add_get(path='/stream_greetings', handler=handler.stream_greetings)
    app.add_subapp(prefix='/greeter', subapp=sub)

class UsersHandler:

    def __init__(self, impl: my_service.core.greeter.greeter.UserManager, executor: typing.Optional[concurrent.futures.Executor]=None) -> None:
        self.__impl = impl
        self.__executor = executor

    async def find_by_name(self, raw_request: aiohttp.web.Request) -> aiohttp.web.Response:
        request = api.aiohttp.model.UsersFindByNameRequest.model_validate_json(await raw_request.read())
        input_name = request.name
        output = await self.__impl.find_by_name(name=input_name)
        response = api.aiohttp.model.UsersFindByNameResponse(payload=api.aiohttp.model.UserInfo(id_=output.id_, name=output.name) if output is not None else None)
        return aiohttp.web.json_response(data=response.model_dump(mode='json', by_alias=True, exclude_none=True))

    async def register(self, raw_request: aiohttp.web.Request) -> aiohttp.web.Response:
        request = api.aiohttp.model.UsersRegisterRequest.model_validate_json(await raw_request.read())
        input_name = request.name
        output = await self.__impl.register(name=input_name)
        response = api.aiohttp.model.UsersRegisterResponse(payload=api.aiohttp.model.UserInfo(id_=output.id_, name=output.name))
        return aiohttp.web.json_response(data=response.model_dump(mode='json', by_alias=True, exclude_none=True))

def add_users_subapp(app: aiohttp.web.Application, handler: UsersHandler) -> None:
    sub = aiohttp.web.Application()
    sub.router.add_post(path='/find_by_name', handler=handler.find_by_name)
    sub.router.add_post(path='/register', handler=handler.register)
    app.add_subapp(prefix='/users', subapp=sub)