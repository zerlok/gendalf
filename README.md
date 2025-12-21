<div align="center">
<img src="https://raw.githubusercontent.com/zerlok/gendalf/main/docs/gendalf-logo.svg" alt="Gendalf Logo" width="800">

[![Latest Version](https://img.shields.io/pypi/v/gendalf.svg)](https://pypi.python.org/pypi/gendalf) [![Python Supported Versions](https://img.shields.io/pypi/pyversions/gendalf.svg)](https://pypi.python.org/pypi/gendalf) [![MyPy Strict](https://img.shields.io/badge/mypy-strict-blue)](https://mypy.readthedocs.io/en/stable/getting_started.html#strict-mode-and-configuration) [![Test Coverage](https://codecov.io/gh/zerlok/gendalf/branch/main/graph/badge.svg)](https://codecov.io/gh/zerlok/gendalf) [![Downloads](https://img.shields.io/pypi/dm/gendalf.svg)](https://pypistats.org/packages/gendalf) [![GitHub stars](https://img.shields.io/github/stars/zerlok/gendalf)](https://github.com/zerlok/gendalf/stargazers)

*You shall pass... your code to adapters!*
</div>

---

**Gendalf** is a code-first code generator for Python adapters.

It generates **type-safe transport and persistence layers** directly from your existing Python code and SQL files —
without requiring OpenAPI, Protobuf, AsyncAPI, or ORMs.

Your code stays the source of truth.
Gendalf generates the glue.

---

### Key ideas

* **Code-first**

    * Adapters are generated from Python modules and SQL files
    * No external specs to maintain

* **Adapter-oriented**

    * Transport adapters: FastAPI servers, HTTP clients, gRPC, websockets
    * Persistence adapters: SQL → typed Python APIs

* **Type-safe**

    * Python types propagate across generated code
    * SQL queries generate typed inputs and outputs

* **Minimal opt-in**

    * Mark Python public classes with `@entrypoint`
    * Annotate SQL queries with `-- sqlcast`
    * Everything else is inferred

---

### Why Gendalf

Most code generators require you to:

* write specs first,
* duplicate models,
* adopt specific frameworks or ORMs.

Gendalf does the opposite:

* your code defines the contract,
* SQL defines persistence,
* adapters & DTO are generated automatically.

---

## Transports & frameworks

### FastAPI & HTTPX

Run with `gendalf src cast fastapi`. It supports:

- request-response (POST method, request & response in HTTP body in JSON format)
- duplex streaming (WebSocket, requests & responses are in WS frames in JSON format)

#### What’s Generated

* `src/api/fastapi/models.py`: Pydantic models for requests and responses that mirror the domain objects. Used by
  `client.py` and `server.py`
* `src/api/fastapi/client.py`: Client classes with async methods, ready to make API calls with appropriate typings for
  request and
  response data.
* `src/api/fastapi/server.py`: Server handler classes, which include data serialization and domain logic invocation.

The generated code is complete, with no need for additional modifications.

### Aiohttp

Run with `gendalf src cast aiohttp`. It supports:

- request-response (POST method, request & response in HTTP body in JSON format)
- duplex streaming (WebSocket, requests & responses are in WS frames in JSON format)

#### What’s Generated

* `src/api/aiohttp/models.py`: Pydantic models for requests and responses that mirror the domain objects. Used by
  `client.py` and `server.py`
* `src/api/aiohttp/client.py`: Client classes with async methods, ready to make API calls with appropriate typings for
  request and
  response data.
* `src/api/aiohttp/server.py`: Server handler classes, which include data serialization and domain logic invocation.

#### Examples

- [my greeter](https://raw.githubusercontent.com/zerlok/gendalf/main/examples/my_greeter)

### SQL

**WIP: generate python type safe code to invoke SQL**

### gRPC (not supported yet)

**This framework support is not supported yet.**

- unary-unary
- stream-stream
- unary-stream
- stream-unary
