import builtins
import dataclasses
import datetime

@dataclasses.dataclass(frozen=True)
class UsersRow:
    id: builtins.int
    name: builtins.str
    created_at: datetime.datetime