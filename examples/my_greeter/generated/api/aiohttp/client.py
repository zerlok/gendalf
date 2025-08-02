import aiohttp
import api.aiohttp.model
import asyncio
import typing

class GreeterClient:

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.__session = session

    async def greet(self, request: api.aiohttp.model.GreeterGreetRequest) -> api.aiohttp.model.GreeterGreetResponse:
        async with self.__session.post(url='/greeter/greet', json=request.model_dump(mode='json', by_alias=True, exclude_none=True)) as raw_response:
            response = api.aiohttp.model.GreeterGreetResponse.model_validate_json(await raw_response.read())
            return response

    async def notify_greeted(self, request: api.aiohttp.model.GreeterNotifyGreetedRequest) -> None:
        async with self.__session.post(url='/greeter/notify_greeted', json=request.model_dump(mode='json', by_alias=True, exclude_none=True)) as raw_response:
            pass

    async def stream_greetings(self, requests: typing.AsyncIterable[api.aiohttp.model.GreeterStreamGreetingsRequest]) -> typing.AsyncIterable[api.aiohttp.model.GreeterStreamGreetingsResponse]:

        async def send_requests(ws: aiohttp.ClientWebSocketResponse) -> None:
            try:
                async for request in requests:
                    await ws.send_json(request.model_dump(mode='json', by_alias=True, exclude_none=True))
            finally:
                await ws.close()
        async with self.__session.ws_connect(url='/greeter/stream_greetings') as ws:
            sender = asyncio.create_task(send_requests(ws))
            try:
                while not ws.closed:
                    msg = await ws.receive()
                    if ws.closed:
                        break
                    if msg.type in {aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE}:
                        continue
                    if msg.type is aiohttp.WSMsgType.ERROR:
                        raise msg.data
                    response = api.aiohttp.model.GreeterStreamGreetingsResponse.model_validate_json(msg.data)
                    yield response
            finally:
                await sender

class UsersClient:

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.__session = session

    async def find_by_name(self, request: api.aiohttp.model.UsersFindByNameRequest) -> api.aiohttp.model.UsersFindByNameResponse:
        async with self.__session.post(url='/users/find_by_name', json=request.model_dump(mode='json', by_alias=True, exclude_none=True)) as raw_response:
            response = api.aiohttp.model.UsersFindByNameResponse.model_validate_json(await raw_response.read())
            return response

    async def register(self, request: api.aiohttp.model.UsersRegisterRequest) -> api.aiohttp.model.UsersRegisterResponse:
        async with self.__session.post(url='/users/register', json=request.model_dump(mode='json', by_alias=True, exclude_none=True)) as raw_response:
            response = api.aiohttp.model.UsersRegisterResponse.model_validate_json(await raw_response.read())
            return response