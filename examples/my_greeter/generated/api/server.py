import api.model
import fastapi
import my_service.core.greeter.greeter
import my_service.core.greeter.model
import typing

class GreeterHandler:

    def __init__(self, impl: my_service.core.greeter.greeter.Greeter) -> None:
        self.__impl = impl

    async def greet(self, request: api.model.GreeterGreetRequest) -> api.model.GreeterGreetResponse:
        input_user = my_service.core.greeter.model.UserInfo(id_=request.user.id_, name=request.user.name)
        output = self.__impl.greet(user=input_user)
        response = api.model.GreeterGreetResponse(payload=output)
        return response

    async def notify_greeted(self, request: api.model.GreeterNotifyGreetedRequest) -> None:
        input_user = my_service.core.greeter.model.UserInfo(id_=request.user.id_, name=request.user.name)
        input_message = request.message
        self.__impl.notify_greeted(user=input_user, message=input_message)

    async def stream_greetings(self, websocket: fastapi.WebSocket) -> None:

        async def receive_inputs() -> typing.AsyncIterator[my_service.core.greeter.model.UserInfo]:
            async for request_text in websocket.iter_text():
                request = api.model.GreeterStreamGreetingsRequest.model_validate_json(request_text)
                yield my_service.core.greeter.model.UserInfo(id_=request.users.id_, name=request.users.name)
        try:
            await websocket.accept()
            async for output in self.__impl.stream_greetings(receive_inputs()):
                response = api.model.GreeterStreamGreetingsResponse(payload=output)
                await websocket.send_text(response.model_dump_json(by_alias=True, exclude_none=True))
        except fastapi.WebSocketDisconnect:
            pass

def create_greeter_router(handler: GreeterHandler) -> fastapi.APIRouter:
    router = fastapi.APIRouter(prefix='/greeter', tags=['Greeter'])
    router.post(path='/greet', description='Make a greeting message for a user.')(handler.greet)
    router.post(path='/notify_greeted', description=None)(handler.notify_greeted)
    router.websocket(path='/stream_greetings')(handler.stream_greetings)
    return router

class UsersHandler:

    def __init__(self, impl: my_service.core.greeter.greeter.UserManager) -> None:
        self.__impl = impl

    async def find_by_name(self, request: api.model.UsersFindByNameRequest) -> api.model.UsersFindByNameResponse:
        input_name = request.name
        output = self.__impl.find_by_name(name=input_name)
        response = api.model.UsersFindByNameResponse(payload=api.model.UserInfo(id_=output.id_, name=output.name) if output is not None else None)
        return response

    async def register(self, request: api.model.UsersRegisterRequest) -> api.model.UsersRegisterResponse:
        input_name = request.name
        output = self.__impl.register(name=input_name)
        response = api.model.UsersRegisterResponse(payload=api.model.UserInfo(id_=output.id_, name=output.name))
        return response

def create_users_router(handler: UsersHandler) -> fastapi.APIRouter:
    router = fastapi.APIRouter(prefix='/users', tags=['Users'])
    router.post(path='/find_by_name', description=None)(handler.find_by_name)
    router.post(path='/register', description='Register user with provided name.')(handler.register)
    return router