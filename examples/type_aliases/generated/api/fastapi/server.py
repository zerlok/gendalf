import api.fastapi.model
import fastapi
import type_aliases.notifier
import typing

class NotifierHandler:

    def __init__(self, impl: type_aliases.notifier.Notifier) -> None:
        self.__impl = impl

    async def subscribe(self, websocket: fastapi.WebSocket) -> None:

        async def receive_inputs() -> typing.AsyncIterator[type_aliases.notifier.Income]:
            async for request_text in websocket.iter_text():
                request = api.fastapi.model.NotifierSubscribeRequest.model_validate_json(request_text)
                yield (type_aliases.notifier.Init(heartbeat=request.options.heartbeat) if isinstance(request.options, api.fastapi.model.Init) else type_aliases.notifier.Cancel())
        try:
            await websocket.accept()
            async for output in self.__impl.subscribe(receive_inputs()):
                response = api.fastapi.model.NotifierSubscribeResponse(payload=api.fastapi.model.Started() if isinstance(output, type_aliases.notifier.Started) else api.fastapi.model.Heartbeat() if isinstance(output, type_aliases.notifier.Heartbeat) else api.fastapi.model.Ended())
                await websocket.send_text(response.model_dump_json(by_alias=True, exclude_none=True))
        except fastapi.WebSocketDisconnect:
            pass

def create_notifier_router(handler: NotifierHandler) -> fastapi.APIRouter:
    router = fastapi.APIRouter(prefix='/notifier', tags=['Notifier'])
    router.websocket(path='/subscribe')(handler.subscribe)
    return router