# Gendalf

[![Latest Version](https://img.shields.io/pypi/v/gendalf.svg)](https://pypi.python.org/pypi/gendalf)
[![Python Supported Versions](https://img.shields.io/pypi/pyversions/gendalf.svg)](https://pypi.python.org/pypi/gendalf)
[![MyPy Strict](https://img.shields.io/badge/mypy-strict-blue)](https://mypy.readthedocs.io/en/stable/getting_started.html#strict-mode-and-configuration)
[![Test Coverage](https://codecov.io/gh/zerlok/gendalf/branch/main/graph/badge.svg)](https://codecov.io/gh/zerlok/gendalf)
[![Downloads](https://img.shields.io/pypi/dm/gendalf.svg)](https://pypistats.org/packages/gendalf)
[![GitHub stars](https://img.shields.io/github/stars/zerlok/gendalf)](https://github.com/zerlok/gendalf/stargazers)

*You shall pass... your domain to transport!*

**Gendalf** is a Python code generation tool that simplifies the creation of **transport layer** code based on
**Domain-Driven Design (DDD)** principles. With **gendalf**, you can effortlessly generate FastAPI, HTTPX, gRPC,
aiohttp, and other transport framework code from your domain layer, ensuring that your business logic remains untouched
while automating the generation of transport-related code.

## Key Features

- **Domain-Driven Design (DDD) approach**: Keeps your business logic in the domain layer and generates the transport
  layer automatically.
- **Multi-transport framework support**: Supports FastAPI and HTTPX (next in line: gRPC; and more frameworks planned for
  future versions).
- **Powered by [astlab](https://github.com/zerlok/astlab) generator**: Uses Python's built-in Abstract Syntax Tree (AST)
  to generate Python modules from your domain entities and interfaces.

## Why gendalf?

With **gendalf**, you don’t have to worry about manually wiring your domain logic to transport code. Whether you're
building APIs, microservices, or handling complex asynchronous communication, **gendalf** automates the transport layer
creation: handles repetitive and error-prone process of writing endpoint handlers and clients from scratch, letting you
focus on what matters most: your business logic.

### Target Audience

This tool is designed for Python developers working on services that follow the Domain-Driven Design (DDD) approach.
It's particularly useful for:

* Teams focusing on business logic without needing to handle the intricacies of APIs or transport layers.
* Developers building Python API services.
* Those looking for a way to streamline the development of API endpoints and client calls without the overhead of
  boilerplate code.

### Comparison with existing codegen solutions

There are many tools for code generation in the Python ecosystem, but most are focused on simplifying specific tasks
like serialization, or generating CRUD / REST operations. Here’s how **gendalf** project differs:

* **Domain-Driven Design (DDD) Focus:** Unlike other code generation tools that focus on CRUD or specific transport
  protocols, this project fully integrates with a DDD approach. This means developers work on the domain layer and let
  the tool handle the presentation layer (API endpoints and clients).
* **Fully Automated Code Generation:** The generated code for the server and client is complete and doesn’t require
  further modifications, saving time and reducing boilerplate.
* **Cross-Transport Flexibility:** Currently, it supports FastAPI and HTTPX, but future versions will add gRPC support,
  allowing developers to generate code for various transport mechanisms without changing their domain logic.

E.g. `grpcio-tools` requires `.proto` files specification first and generates client stubs & server interface, so on the
server side an additional code is required: implement request deserialization from protobuf python classes to domain
(value objects), invoke domain layer and then serialize protobuf response.

## Transports & frameworks

### FastAPI & HTTPX

Run with `gendalf src cast fastapi`. It supports:

- request-response (POST method, request & response in HTTP body in JSON format)
- duplex streaming (WebSocket, requests & responses are in WS frames in JSON format)

#### What’s Generated

* `src/api/models.py`: Pydantic models for requests and responses that mirror the domain objects. Used by `client.py` and `server.py`
* `src/api/client.py`: Client classes with async methods, ready to make API calls with appropriate typings for request and
  response data.
* `src/api/server.py`: Server handler classes, which include data serialization and domain logic invocation.

The generated code is complete, with no need for additional modifications.

#### Examples

- [my greeter](examples/my_greeter)

### gRPC (not supported yet)

**This framework support is not supported yet.**

- unary-unary
- stream-stream
- unary-stream
- stream-unary
