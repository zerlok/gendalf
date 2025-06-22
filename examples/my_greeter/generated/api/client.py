import api.model
import asyncio
import httpx
import httpx_ws
import typing

class GreeterAsyncClient:

    def __init__(self, impl: httpx.AsyncClient) -> None:
        self.__impl = impl

    async def greet(self, request: api.model.GreeterGreetRequest) -> api.model.GreeterGreetResponse:
        raw_response = await self.__impl.post(url='/greeter/greet', json=request.model_dump(by_alias=True, exclude_none=True))
        response = api.model.GreeterGreetResponse.model_validate_json(raw_response.read())
        return response

    async def notify_greeted(self, request: api.model.GreeterNotifyGreetedRequest) -> None:
        await self.__impl.post(url='/greeter/notify_greeted', json=request.model_dump(by_alias=True, exclude_none=True))

    async def stream_greetings(self, requests: typing.AsyncIterable[api.model.GreeterStreamGreetingsRequest]) -> typing.AsyncIterable[api.model.GreeterStreamGreetingsResponse]:

        async def send_requests(ws: httpx_ws.AsyncWebSocketSession) -> None:
            try:
                async for request in requests:
                    await ws.send_text(request.model_dump_json(by_alias=True, exclude_none=True))
            finally:
                await ws.close()
        async with httpx_ws.aconnect_ws(url='/greeter/stream_greetings', client=self.__impl) as ws, asyncio.TaskGroup() as tasks:
            sender = tasks.create_task(send_requests(ws))
            while not sender.done():
                try:
                    raw_response = await ws.receive_text()
                except (httpx_ws.WebSocketNetworkError, httpx_ws.WebSocketDisconnect) as err:
                    if sender.done():
                        break
                    raise err
                else:
                    response = api.model.GreeterStreamGreetingsResponse.model_validate_json(raw_response)
                    yield response

class UsersAsyncClient:

    def __init__(self, impl: httpx.AsyncClient) -> None:
        self.__impl = impl

    async def find_by_name(self, request: api.model.UsersFindByNameRequest) -> api.model.UsersFindByNameResponse:
        raw_response = await self.__impl.post(url='/users/find_by_name', json=request.model_dump(by_alias=True, exclude_none=True))
        response = api.model.UsersFindByNameResponse.model_validate_json(raw_response.read())
        return response

    async def register(self, request: api.model.UsersRegisterRequest) -> api.model.UsersRegisterResponse:
        raw_response = await self.__impl.post(url='/users/register', json=request.model_dump(by_alias=True, exclude_none=True))
        response = api.model.UsersRegisterResponse.model_validate_json(raw_response.read())
        return response