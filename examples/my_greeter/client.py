import asyncio
import sys
import time
import typing as t

import httpx
from api.fastapi.client import GreeterAsyncClient, GreeterClient
from api.fastapi.model import GreeterGreetRequest, GreeterStreamGreetingsRequest, UserInfo


def main() -> None:
    with httpx.Client(base_url="http://localhost:8000") as client:
        greeter = GreeterClient(client)

        print("unary unary request")
        response = greeter.greet(GreeterGreetRequest(user=UserInfo(id_=42, name="John")))
        print(response.payload)

        print("stream stream request")

        def iter_requests() -> t.Iterator[GreeterStreamGreetingsRequest]:
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Bob"))
            time.sleep(0.5)
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=44, name="Phill"))
            time.sleep(0.5)

        for chunk in greeter.stream_greetings(iter_requests(), receive_timeout=1.0):
            print(chunk.payload)


async def main_async() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        greeter = GreeterAsyncClient(client)

        print("unary unary request")
        response = await greeter.greet(GreeterGreetRequest(user=UserInfo(id_=42, name="John")))
        print(response.payload)

        print("stream stream request")

        async def iter_requests() -> t.AsyncIterator[GreeterStreamGreetingsRequest]:
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Bob"))
            await asyncio.sleep(0.5)
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=44, name="Phill"))
            await asyncio.sleep(0.5)

        async for chunk in greeter.stream_greetings(iter_requests()):
            print(chunk.payload)


if __name__ == "__main__":
    if "--async" in sys.argv:
        asyncio.run(main_async())

    else:
        main()
