import abc
import asyncio
import typing as t
from contextlib import asynccontextmanager
from functools import partial, wraps

import pytest
from _pytest.fixtures import SubRequest
from aiohttp.test_utils import TestServer, unused_port
from fastapi import FastAPI
from uvicorn import Config, Server

from examples.my_greeter.client import run_client_aiohttp, run_client_httpx_async, run_client_httpx_sync
from examples.my_greeter.server import create_aiohttp, create_fastapi
from gendalf._typing import ParamSpec

P = ParamSpec("P")
V_co = t.TypeVar("V_co", covariant=True)


class ServerRunner(t.Protocol):
    @abc.abstractmethod
    def __call__(self, *, host: str, port: int) -> t.AsyncContextManager[object]:
        raise NotImplementedError


class ClientRunner(t.Protocol):
    @abc.abstractmethod
    async def __call__(self, *, host: str, port: int) -> object:
        raise NotImplementedError


async def test_server_client_can_communicate(
    server_runner: ServerRunner,
    client_runner: ClientRunner,
    server_host: str,
    server_port: int,
) -> None:
    async with server_runner(host=server_host, port=server_port):
        await client_runner(host=server_host, port=server_port)


@pytest.fixture
def server_host() -> str:
    return "localhost"


@pytest.fixture
def server_port() -> int:
    return unused_port()


@pytest.fixture(params=["fastapi", "aiohttp"])
def server_runner(request: SubRequest) -> ServerRunner:
    if request.param == "fastapi":
        return partial(run_fastapi_server, create_fastapi())

    elif request.param == "aiohttp":
        return partial(TestServer, create_aiohttp([]))

    else:
        msg = "unknown server kind"
        raise ValueError(msg, request.param)


@pytest.fixture(params=["httpx", "httpx-async", "aiohttp"])
def client_runner(request: SubRequest) -> ClientRunner:
    if request.param == "httpx":
        return sync2async(run_client_httpx_sync)

    elif request.param == "httpx-async":
        return run_client_httpx_async

    elif request.param == "aiohttp":
        return run_client_aiohttp

    else:
        msg = "unknown server kind"
        raise ValueError(msg, request.param)


def sync2async(func: t.Callable[P, V_co]) -> t.Callable[P, t.Coroutine[t.Any, t.Any, V_co]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> V_co:  # type: ignore[misc]
        return await asyncio.get_event_loop().run_in_executor(None, partial(func, *args, **kwargs))

    return wrapper


@asynccontextmanager
async def run_fastapi_server(app: FastAPI, host: str, port: int, check_started: float = 0.1) -> t.AsyncIterator[Server]:
    server = Server(Config(app, host=host, port=port, log_config=None))
    task = asyncio.create_task(server.serve())

    try:
        # NOTE: the only way to check if server was started - is to check `started` flag in while loop.
        while not server.started:  # noqa: ASYNC110
            await asyncio.sleep(check_started)

        yield server

    finally:
        server.should_exit = True
        await task
