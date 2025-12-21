import api.fastapi.model
import asyncio
import builtins
import httpx
import httpx_ws
import queue
import threading
import typing

class NotifierClient:

    def __init__(self, impl: httpx.Client) -> None:
        self.__impl = impl

    def subscribe(self, requests: typing.Iterable[api.fastapi.model.NotifierSubscribeRequest], receive_timeout: typing.Optional[builtins.float]=None) -> typing.Iterator[api.fastapi.model.NotifierSubscribeResponse]:
        done = threading.Event()

        def send_requests(ws: httpx_ws.WebSocketSession) -> None:
            done.clear()
            try:
                for request in requests:
                    ws.send_text(request.model_dump_json(by_alias=True, exclude_none=True))
            finally:
                done.set()
                ws.close()
        with httpx_ws.connect_ws(url='/notifier/subscribe', client=self.__impl) as ws:
            sender = threading.Thread(target=send_requests, args=(ws,), daemon=True)
            sender.start()
            while not done.is_set():
                try:
                    raw_response = ws.receive_text(timeout=receive_timeout)
                except queue.Empty:
                    continue
                except (httpx_ws.WebSocketNetworkError, httpx_ws.WebSocketDisconnect) as err:
                    if done.is_set():
                        break
                    raise err
                else:
                    response = api.fastapi.model.NotifierSubscribeResponse.model_validate_json(raw_response)
                    yield response

class NotifierAsyncClient:

    def __init__(self, impl: httpx.AsyncClient) -> None:
        self.__impl = impl

    async def subscribe(self, requests: typing.AsyncIterable[api.fastapi.model.NotifierSubscribeRequest], receive_timeout: typing.Optional[builtins.float]=None) -> typing.AsyncIterator[api.fastapi.model.NotifierSubscribeResponse]:

        async def send_requests(ws: httpx_ws.AsyncWebSocketSession) -> None:
            try:
                async for request in requests:
                    await ws.send_text(request.model_dump_json(by_alias=True, exclude_none=True))
            finally:
                await ws.close()
        async with httpx_ws.aconnect_ws(url='/notifier/subscribe', client=self.__impl) as ws:
            sender = asyncio.create_task(send_requests(ws))
            try:
                while not sender.done():
                    try:
                        raw_response = await ws.receive_text(timeout=receive_timeout)
                    except queue.Empty:
                        continue
                    except (httpx_ws.WebSocketNetworkError, httpx_ws.WebSocketDisconnect) as err:
                        if sender.done():
                            break
                        raise err
                    else:
                        response = api.fastapi.model.NotifierSubscribeResponse.model_validate_json(raw_response)
                        yield response
            finally:
                await sender