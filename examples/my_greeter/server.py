from api.server import GreeterHandler, UsersHandler, create_greeter_router, create_users_router
from fastapi import FastAPI
from my_service.core.greeter.greeter import Greeter, UserManager
from my_service.core.message.generator import FstringMessageGenerator


def create_app() -> FastAPI:
    greeter = Greeter(FstringMessageGenerator("Hello, {user.name}"))
    user_manager = UserManager()

    app = FastAPI()
    app.include_router(create_greeter_router(GreeterHandler(greeter)))
    app.include_router(create_users_router(UsersHandler(user_manager)))

    return app
