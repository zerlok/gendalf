# gendalf codegen example

## Usage

Currently, supports **python 3.12 and higher**.

1) Pull & install the project from github (pypi will be added in the future).
2) Install project dependencies and extras (e.g. with poetry `poetry install --all-extras`)
    1) this will add `gendalf` CLI to virtual environment, CLI code
       is [here](../../src/gendalf/cli.py).
3) add `@entrypoint` decorators to top-level classes in your domain layer code (
   e.g. [greeter](src/my_service/core/greeter/greeter.py))
4) enter the root directory of your project (e.g. [the directory of this readme file](./))
5) enter the virtual env (e.g. `poetry shell`)
6) you can check which entrypoints & methods `gendalf` sees with `gendalf --ignore-module-on-import-error src show`
6) run codegen with `gendalf gen src fastapi --ignore-module-on-import-error` (e.g. this will generate `src/api` directory
   with python modules for this example project)
7) write server assembling code (e.g. [greeter server](src/my_service/server.py))
8) write client top-level code (e.g. [greeter client](client.py))
9) run server & client (don't forget to add src to python path, e.g. via env `PYTHONPATH=src`)
    1) `PYTHONPATH=src poetry run uvicorn --factory my_service.test_server:create_app`
    2) `PYTHONPATH=src poetry run python test_client.py`

**What’s Generated:**

* **api/models.py**: Pydantic models for requests and responses that mirror the domain objects.
* **api/client.py**: Client classes with async methods, ready to make API calls with appropriate typings for request and
  response data.
* **api/server.py**: Server handler classes, which include data serialization and domain logic invocation.

The generated code is complete, with no need for additional modifications.
