import aiohttp
import api.aiohttp.model
import asyncio
import typing

class NotifierClient:

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.__session = session

    async def subscribe(self, requests: typing.AsyncIterable[api.aiohttp.model.NotifierSubscribeRequest]) -> typing.AsyncIterator[api.aiohttp.model.NotifierSubscribeResponse]:

        async def send_requests(ws: aiohttp.ClientWebSocketResponse) -> None:
            try:
                async for request in requests:
                    await ws.send_json(request.model_dump(mode='json', by_alias=True, exclude_none=True))
            finally:
                await ws.close()
        async with self.__session.ws_connect(url='/notifier/subscribe') as ws:
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
                    response = api.aiohttp.model.NotifierSubscribeResponse.model_validate_json(msg.data)
                    yield response
            finally:
                await sender