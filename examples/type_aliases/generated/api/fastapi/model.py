import datetime
import pydantic
import typing

class Init(pydantic.BaseModel):
    """DTO for :class:`type_aliases.notifier.Init` type."""
    heartbeat: datetime.timedelta

class Cancel(pydantic.BaseModel):
    """DTO for :class:`type_aliases.notifier.Cancel` type."""
type Income = typing.Union[Init, Cancel]

class NotifierSubscribeRequest(pydantic.BaseModel):
    """Request DTO for :class:`type_aliases.notifier.Notifier` :meth:`subscribe` entrypoint method."""
    options: Income

class Started(pydantic.BaseModel):
    """DTO for :class:`type_aliases.notifier.Started` type."""

class Heartbeat(pydantic.BaseModel):
    """DTO for :class:`type_aliases.notifier.Heartbeat` type."""

class Ended(pydantic.BaseModel):
    """DTO for :class:`type_aliases.notifier.Ended` type."""
type Outcome = typing.Union[Started, Heartbeat, Ended]

class NotifierSubscribeResponse(pydantic.BaseModel):
    """Response DTO for :class:`type_aliases.notifier.Notifier` :meth:`subscribe` entrypoint method."""
    payload: Outcome