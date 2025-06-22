import builtins
import pydantic
import typing

class UserInfo(pydantic.BaseModel):
    """DTO for `my_service.core.greeter.model.UserInfo` type"""
    id_: builtins.int
    name: builtins.str

class GreeterGreetRequest(pydantic.BaseModel):
    """Request DTO for :class:`my_service.core.greeter.greeter.Greeter` :meth:`greet` entrypoint method"""
    user: UserInfo

class GreeterGreetResponse(pydantic.BaseModel):
    """Response DTO for :class:`my_service.core.greeter.greeter.Greeter` :meth:`greet` entrypoint method"""
    payload: builtins.str

class GreeterNotifyGreetedRequest(pydantic.BaseModel):
    """Request DTO for :class:`my_service.core.greeter.greeter.Greeter` :meth:`notify_greeted` entrypoint method"""
    user: UserInfo
    message: builtins.str

class GreeterStreamGreetingsRequest(pydantic.BaseModel):
    """Request DTO for :class:`my_service.core.greeter.greeter.Greeter` :meth:`stream_greetings` entrypoint method"""
    users: UserInfo

class GreeterStreamGreetingsResponse(pydantic.BaseModel):
    """Response DTO for :class:`my_service.core.greeter.greeter.Greeter` :meth:`stream_greetings` entrypoint method"""
    payload: builtins.str

class UsersFindByNameRequest(pydantic.BaseModel):
    """Request DTO for :class:`my_service.core.greeter.greeter.UserManager` :meth:`find_by_name` entrypoint method"""
    name: builtins.str

class UsersFindByNameResponse(pydantic.BaseModel):
    """Response DTO for :class:`my_service.core.greeter.greeter.UserManager` :meth:`find_by_name` entrypoint method"""
    payload: typing.Optional[UserInfo]

class UsersRegisterRequest(pydantic.BaseModel):
    """Request DTO for :class:`my_service.core.greeter.greeter.UserManager` :meth:`register` entrypoint method"""
    name: builtins.str

class UsersRegisterResponse(pydantic.BaseModel):
    """Response DTO for :class:`my_service.core.greeter.greeter.UserManager` :meth:`register` entrypoint method"""
    payload: UserInfo