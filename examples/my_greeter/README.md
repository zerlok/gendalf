# gendalf codegen example (my greeter & users)

## Project structure

* `src`: Python code of the service that provides greeter & users functionality. `Greeter` and `UserManager` domain
  classes has `entrypoint` marker.
* `generated`: Python code that was generated with `gendalf`.
    * `api/models.py`: Pydantic models for requests and responses that mirror the domain objects. Used by both client
      and server.
    * `api/client.py`: Client SDK. Python classes with async methods, ready to make API calls with appropriate typings
      for request and response data.
    * `api/server.py`: Server handlers & router factory functions, which include endpoint setup, data serialization and
      domain logic invocation.
* `client.py`: Example of client SDK usage.
* `server.py`: Example of server generated code usage.

## Generate code

1) Enter the directory of this example.
2) Run `poetry run gendalf src show`. This will inspect the code in `src` dir for [
   `entrypoint`](../../src/gendalf/entrypoint/decorator.py) decorators.
   ```
   $ poetry run gendalf src show
   * Greeter (my_service.core.greeter.greeter.Greeter)
       * greet(user: my_service.core.greeter.model.UserInfo) -> builtins.str
         """Make a greeting message for a user."""
       * notify_greeted(user: my_service.core.greeter.model.UserInfo, message: builtins.str)
       * stream_greetings(users: typing.Iterator[my_service.core.greeter.model.UserInfo]) -> typing.Iterator[builtins.str]

   * Users (my_service.core.greeter.greeter.UserManager)
       * find_by_name(name: builtins.str) -> typing.Optional[my_service.core.greeter.model.UserInfo]
       * register(name: builtins.str) -> my_service.core.greeter.model.UserInfo
         """Register user with provided name."""
   ```
3) Run `poetry run gendalf src cast --output generated fastapi`. This will generate the code in `generated` directory
   using FastAPI & httpx & pydantic libraries. The generated code is complete, with no need for additional
   modifications.
4) Run server & client (don't forget to add src to python path, e.g. via env `PYTHONPATH=src:generated`)
    1) `PYTHONPATH=src:generated poetry run uvicorn --factory server:create_app`
    2) `PYTHONPATH=src:generated poetry run python client.py`
5) You can play with it more, try to modify some fields in `src` dataclasses or add more methods to `Greeter` or `Users`
   and see how `gendalf` reacts on that changes (repeat steps 2 / 3).
