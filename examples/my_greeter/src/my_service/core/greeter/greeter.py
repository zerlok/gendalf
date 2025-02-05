import typing as t

from gendalf.entrypoint.decorator import entrypoint
from my_service.core.greeter.abc import MessageGenerator
from my_service.core.greeter.model import UserInfo


@entrypoint
class Greeter:
    def __init__(self, greeting: MessageGenerator) -> None:
        self.__greeting = greeting
        self.__previous: list[str] = []

    def greet(self, user: UserInfo) -> str:
        """Make a greeting message for a user."""
        return self.__greeting.gen_message({"user": user, "previous_greetings": self.__previous})

    def notify_greeted(self, user: UserInfo, message: str) -> None:
        self.__previous.append(message)

    async def stream_greetings(self, users: t.AsyncIterator[UserInfo]) -> t.AsyncIterator[str]:
        async for user in users:
            yield self.greet(user)


@entrypoint(name="Users")
class UserManager:
    def __init__(self) -> None:
        self.__users = set[UserInfo]()

    def register(self, name: str) -> UserInfo:
        """Register user with provided name."""
        user = UserInfo(id_=len(self.__users) + 1, name=name)
        self.__users.add(user)

        return user

    def find_by_name(self, name: str) -> t.Optional[UserInfo]:
        for user in self.__users:
            if user.name == name:
                return user

        return None
