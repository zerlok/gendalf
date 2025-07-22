import api.fastapi.model
import asyncio
import httpx
import httpx_ws
import threading
import typing

class GreeterClient:

    def __init__(self, impl: httpx.Client) -> None:
        self.__impl = impl

    def greet(self, request: api.fastapi.model.GreeterGreetRequest) -> api.fastapi.model.GreeterGreetResponse:
        raw_response = self.__impl.post(url='/greeter/greet', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))
        response = api.fastapi.model.GreeterGreetResponse.model_validate_json(raw_response.read())
        return response

    def notify_greeted(self, request: api.fastapi.model.GreeterNotifyGreetedRequest) -> None:
        self.__impl.post(url='/greeter/notify_greeted', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))

    def stream_greetings(self, requests: typing.Iterable[api.fastapi.model.GreeterStreamGreetingsRequest]) -> typing.Iterable[api.fastapi.model.GreeterStreamGreetingsResponse]:

        def send_requests(ws: httpx_ws.WebSocketSession) -> None:
            try:
                for request in requests:
                    ws.send_text(request.model_dump_json(by_alias=True, exclude_none=True))
            finally:
                ws.close()
        with httpx_ws.connect_ws(url='/greeter/stream_greetings', client=self.__impl) as ws:
            sender = threading.Thread(target=send_requests, args=(ws,), daemon=True)
            sender.start()
            while not sender.is_alive():
                try:
                    raw_response = ws.receive_text()
                except (httpx_ws.WebSocketNetworkError, httpx_ws.WebSocketDisconnect) as err:
                    if sender.is_alive():
                        break
                    raise err
                else:
                    response = api.fastapi.model.GreeterStreamGreetingsResponse.model_validate_json(raw_response)
                    yield response

class GreeterAsyncClient:

    def __init__(self, impl: httpx.AsyncClient) -> None:
        self.__impl = impl

    async def greet(self, request: api.fastapi.model.GreeterGreetRequest) -> api.fastapi.model.GreeterGreetResponse:
        raw_response = await self.__impl.post(url='/greeter/greet', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))
        response = api.fastapi.model.GreeterGreetResponse.model_validate_json(raw_response.read())
        return response

    async def notify_greeted(self, request: api.fastapi.model.GreeterNotifyGreetedRequest) -> None:
        await self.__impl.post(url='/greeter/notify_greeted', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))

    async def stream_greetings(self, requests: typing.AsyncIterable[api.fastapi.model.GreeterStreamGreetingsRequest]) -> typing.AsyncIterable[api.fastapi.model.GreeterStreamGreetingsResponse]:

        async def send_requests(ws: httpx_ws.AsyncWebSocketSession) -> None:
            try:
                async for request in requests:
                    await ws.send_text(request.model_dump_json(by_alias=True, exclude_none=True))
            finally:
                await ws.close()
        async with asyncio.TaskGroup() as tasks, httpx_ws.aconnect_ws(url='/greeter/stream_greetings', client=self.__impl) as ws:
            sender = tasks.create_task(send_requests(ws))
            while not sender.done():
                try:
                    raw_response = await ws.receive_text()
                except (httpx_ws.WebSocketNetworkError, httpx_ws.WebSocketDisconnect) as err:
                    if sender.done():
                        break
                    raise err
                else:
                    response = api.fastapi.model.GreeterStreamGreetingsResponse.model_validate_json(raw_response)
                    yield response

class UsersClient:

    def __init__(self, impl: httpx.Client) -> None:
        self.__impl = impl

    def find_by_name(self, request: api.fastapi.model.UsersFindByNameRequest) -> api.fastapi.model.UsersFindByNameResponse:
        raw_response = self.__impl.post(url='/users/find_by_name', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))
        response = api.fastapi.model.UsersFindByNameResponse.model_validate_json(raw_response.read())
        return response

    def register(self, request: api.fastapi.model.UsersRegisterRequest) -> api.fastapi.model.UsersRegisterResponse:
        raw_response = self.__impl.post(url='/users/register', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))
        response = api.fastapi.model.UsersRegisterResponse.model_validate_json(raw_response.read())
        return response

class UsersAsyncClient:

    def __init__(self, impl: httpx.AsyncClient) -> None:
        self.__impl = impl

    async def find_by_name(self, request: api.fastapi.model.UsersFindByNameRequest) -> api.fastapi.model.UsersFindByNameResponse:
        raw_response = await self.__impl.post(url='/users/find_by_name', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))
        response = api.fastapi.model.UsersFindByNameResponse.model_validate_json(raw_response.read())
        return response

    async def register(self, request: api.fastapi.model.UsersRegisterRequest) -> api.fastapi.model.UsersRegisterResponse:
        raw_response = await self.__impl.post(url='/users/register', json=request.model_dump(mode='json', by_alias=True, exclude_none=True))
        response = api.fastapi.model.UsersRegisterResponse.model_validate_json(raw_response.read())
        return response