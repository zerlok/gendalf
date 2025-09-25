import asyncio
import logging
import time
import typing as t
from argparse import ArgumentParser

import aiohttp
import httpx

_LOGGER = logging.getLogger("client")


def run_client_httpx_sync(host: str, port: int) -> None:
    from api.fastapi.client import GreeterClient, UsersClient
    from api.fastapi.model import (
        GreeterGreetRequest,
        GreeterStreamGreetingsRequest,
        UserInfo,
        UsersFindInfoByNameRequest,
    )

    with httpx.Client(base_url=f"http://{host}:{port}") as client:
        greeter = GreeterClient(client)

        _LOGGER.debug("unary unary request")
        response = greeter.greet(GreeterGreetRequest(user=UserInfo(id_=42, name="John")))
        _LOGGER.info(response.payload)

        _LOGGER.debug("stream stream request")

        def iter_requests() -> t.Iterator[GreeterStreamGreetingsRequest]:
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Bob"))
            time.sleep(0.5)
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=44, name="Phill"))
            time.sleep(0.5)

        for chunk in greeter.stream_greetings(iter_requests(), receive_timeout=1.0):
            _LOGGER.info(chunk.payload)

        users = UsersClient(client)
        found = users.find_info_by_name(UsersFindInfoByNameRequest(name="python"))
        _LOGGER.info(found.payload)


async def run_client_httpx_async(host: str, port: int) -> None:
    from api.fastapi.client import GreeterAsyncClient, UsersAsyncClient
    from api.fastapi.model import (
        GreeterGreetRequest,
        GreeterStreamGreetingsRequest,
        UserInfo,
        UsersFindInfoByNameRequest,
    )

    async with httpx.AsyncClient(base_url=f"http://{host}:{port}") as client:
        greeter = GreeterAsyncClient(client)

        _LOGGER.debug("unary unary request")
        response = await greeter.greet(GreeterGreetRequest(user=UserInfo(id_=42, name="John")))
        _LOGGER.info(response.payload)

        _LOGGER.debug("stream stream request")

        async def iter_requests() -> t.AsyncIterator[GreeterStreamGreetingsRequest]:
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Bob"))
            await asyncio.sleep(0.5)
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=44, name="Phill"))
            await asyncio.sleep(0.5)

        async for chunk in greeter.stream_greetings(iter_requests()):
            _LOGGER.info(chunk.payload)

        users = UsersAsyncClient(client)
        found = await users.find_info_by_name(UsersFindInfoByNameRequest(name="python"))
        _LOGGER.info(found.payload)


async def run_client_aiohttp(host: str, port: int) -> None:
    from api.aiohttp.client import GreeterClient, UsersClient
    from api.aiohttp.model import (
        GreeterGreetRequest,
        GreeterStreamGreetingsRequest,
        UserInfo,
        UsersFindInfoByNameRequest,
    )

    async with aiohttp.ClientSession(base_url=f"http://{host}:{port}") as session:
        greeter = GreeterClient(session)

        _LOGGER.debug("unary unary request")
        response = await greeter.greet(GreeterGreetRequest(user=UserInfo(id_=42, name="John")))
        _LOGGER.info(response.payload)

        _LOGGER.debug("stream stream request")

        async def iter_requests() -> t.AsyncIterator[GreeterStreamGreetingsRequest]:
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Bob"))
            await asyncio.sleep(0.5)
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=44, name="Phill"))
            await asyncio.sleep(0.5)

        async for chunk in greeter.stream_greetings(iter_requests()):
            _LOGGER.info(chunk.payload)

        users = UsersClient(session)
        found = await users.find_info_by_name(UsersFindInfoByNameRequest(name="python"))
        _LOGGER.info(found.payload)


def main() -> None:
    parser = ArgumentParser()

    parser.add_argument("kind", choices=["httpx", "aiohttp"])
    parser.add_argument("--async", nargs="?", dest="is_async", const=True, default=False, type=bool)
    parser.add_argument("--host", default="localhost", type=str)
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--log-level", default="INFO", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    ns = parser.parse_args()

    logging.basicConfig(level=logging.getLevelName(ns.log_level))

    if ns.kind == "httpx":
        if ns.is_async:
            asyncio.run(run_client_httpx_async(ns.host, ns.port))

        else:
            run_client_httpx_sync(ns.host, ns.port)

    elif ns.kind == "aiohttp":
        asyncio.run(run_client_aiohttp(ns.host, ns.port))

    else:
        msg = "unknown kind"
        raise ValueError(msg, ns.kind)


if __name__ == "__main__":
    main()
