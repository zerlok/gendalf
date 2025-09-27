import typing as t

from aiohttp import web
from fastapi import FastAPI
from my_service.core.greeter.greeter import Greeter, UserManager
from my_service.core.message.generator import FstringMessageGenerator
from my_service.core.structure import StructureController


def create_struct() -> StructureController:
    return StructureController()


def create_greeter() -> Greeter:
    return Greeter(FstringMessageGenerator("Hello, {user.name}"))


def create_user_manager() -> UserManager:
    return UserManager()


def create_fastapi() -> FastAPI:
    """
    Create a FastAPI application.

    Usage: `uvicorn --factory examples.my_greeter.server:create_fastapi`
    """

    from api.fastapi.server import (
        GreeterHandler,
        StructureHandler,
        UsersHandler,
        create_greeter_router,
        create_structure_router,
        create_users_router,
    )

    app = FastAPI()

    app.include_router(create_structure_router(StructureHandler(create_struct())))
    app.include_router(create_greeter_router(GreeterHandler(create_greeter())))
    app.include_router(create_users_router(UsersHandler(create_user_manager())))

    return app


def create_aiohttp(_: t.Sequence[str]) -> web.Application:
    """
    Create an aiohttp application.

    Usage: `python -m aiohttp.web examples.my_greeter.server:create_aiohttp --port 8000`
    """
    from api.aiohttp.server import (
        GreeterHandler,
        StructureHandler,
        UsersHandler,
        add_greeter_subapp,
        add_structure_subapp,
        add_users_subapp,
    )

    app = web.Application()

    add_structure_subapp(app, StructureHandler(create_struct()))
    add_greeter_subapp(app, GreeterHandler(create_greeter()))
    add_users_subapp(app, UsersHandler(create_user_manager()))

    return app
