import asyncio
import typing as t
from dataclasses import dataclass
from datetime import timedelta

from gendalf.entrypoint.decorator import entrypoint


@dataclass(frozen=True, kw_only=True)
class Init:
    heartbeat: timedelta


@dataclass(frozen=True, kw_only=True)
class Cancel:
    pass


@dataclass(frozen=True, kw_only=True)
class Started:
    pass


@dataclass(frozen=True, kw_only=True)
class Heartbeat:
    pass


@dataclass(frozen=True, kw_only=True)
class Ended:
    pass


type Income = Init | Cancel
type Outcome = Started | Heartbeat | Ended
type Event = Income | Outcome


@entrypoint()
class Notifier:
    async def subscribe(self, options: t.AsyncIterable[Income]) -> t.AsyncIterable[Outcome]:
        done = asyncio.Event()
        queue = asyncio.Queue[Event | None]()

        running = True
        started = False
        consumer = asyncio.create_task(self.__consume(options, queue))
        heartbeat = asyncio.create_task(self.__noop())

        try:
            while running:
                income = await queue.get()
                match income:
                    case Init():
                        heartbeat.cancel()
                        await heartbeat

                        heartbeat = asyncio.create_task(self.__heartbeat(income.heartbeat, queue))
                        queue.put_nowait(Started())

                    case Cancel():
                        consumer.cancel()

                    case Started():
                        started = True
                        yield income

                    case Heartbeat() | Ended():
                        yield income

                    case None:
                        running = False

                    case _:
                        t.assert_never(income)

        finally:
            heartbeat.cancel()
            consumer.cancel()
            await asyncio.gather(consumer, heartbeat)

            if started:
                yield Ended()

    async def __consume(self, options: t.AsyncIterable[Income], queue: asyncio.Queue[Event | None]) -> None:
        try:
            async for opt in options:
                queue.put_nowait(opt)

        finally:
            queue.put_nowait(None)

    async def __heartbeat(self, delay: timedelta, queue: asyncio.Queue[Event | None]) -> None:
        while True:
            await asyncio.sleep(delay.total_seconds())
            queue.put_nowait(Heartbeat())

    async def __noop(self) -> None:
        pass
