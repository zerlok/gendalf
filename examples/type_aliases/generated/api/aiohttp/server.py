import aiohttp.web
import api.aiohttp.model
import concurrent.futures
import type_aliases.notifier
import typing

class NotifierHandler:

    def __init__(self, impl: type_aliases.notifier.Notifier, executor: typing.Optional[concurrent.futures.Executor]=None) -> None:
        self.__impl = impl
        self.__executor = executor

    async def subscribe(self, raw_request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
        websocket = aiohttp.web.WebSocketResponse()

        async def receive_inputs() -> typing.AsyncIterator[type_aliases.notifier.Income]:
            async for msg in websocket:
                request = api.aiohttp.model.NotifierSubscribeRequest.model_validate_json(msg.data)
                yield (type_aliases.notifier.Init(heartbeat=request.options.heartbeat) if isinstance(request.options, api.aiohttp.model.Init) else type_aliases.notifier.Cancel())
        await websocket.prepare(raw_request)
        async for output in self.__impl.subscribe(receive_inputs()):
            response = api.aiohttp.model.NotifierSubscribeResponse(payload=api.aiohttp.model.Started() if isinstance(output, type_aliases.notifier.Started) else api.aiohttp.model.Heartbeat() if isinstance(output, type_aliases.notifier.Heartbeat) else api.aiohttp.model.Ended())
            await websocket.send_str(response.model_dump_json(by_alias=True, exclude_none=True))
        return websocket

def add_notifier_subapp(app: aiohttp.web.Application, handler: NotifierHandler) -> None:
    sub = aiohttp.web.Application()
    sub.router.add_get(path='/subscribe', handler=handler.subscribe)
    app.add_subapp(prefix='/notifier', subapp=sub)