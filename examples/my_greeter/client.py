import asyncio
import typing as t

import httpx
from api.client import GreeterAsyncClient
from api.model import GreeterGreetRequest, GreeterStreamGreetingsRequest, UserInfo


async def main() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        greeter = GreeterAsyncClient(client)

        response = await greeter.greet(GreeterGreetRequest(user=UserInfo(id_=42, name="John")))
        print(response.payload)

        async def iter_requests() -> t.AsyncIterator[GreeterStreamGreetingsRequest]:
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Bob"))
            await asyncio.sleep(0.5)
            yield GreeterStreamGreetingsRequest(users=UserInfo(id_=43, name="Phill"))
            await asyncio.sleep(0.5)

        async for chunk in greeter.stream_greetings(iter_requests()):
            print(chunk.payload)


if __name__ == "__main__":
    asyncio.run(main())
