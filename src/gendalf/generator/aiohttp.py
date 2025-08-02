import typing as t
from contextlib import contextmanager
from functools import cached_property

from astlab import package
from astlab.abc import Expr, TypeDefinitionBuilder, TypeRef
from astlab.builder import (
    AttrASTBuilder,
    ClassScopeASTBuilder,
    ClassTypeRefBuilder,
    ModuleASTBuilder,
    PackageASTBuilder,
    ScopeASTBuilder,
)
from astlab.types import ModuleInfo, NamedTypeInfo, TypeAnnotator, TypeInfo, TypeInspector, TypeLoader

from gendalf._typing import assert_never, override
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.dto.pydantic import PydanticDtoMapper
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult
from gendalf.model import EntrypointInfo, MethodInfo, ParameterInfo, StreamStreamMethodInfo, UnaryUnaryMethodInfo
from gendalf.string_case import camel2snake, snake2camel


class AiohttpModel(TypeDefinitionBuilder):
    def __init__(
        self,
        mapper: PydanticDtoMapper,
        ref: ClassTypeRefBuilder,
    ) -> None:
        self.__mapper = mapper
        self.__ref = ref

    @override
    @property
    def info(self) -> TypeInfo:
        return self.__ref.info

    @override
    def ref(self) -> ClassTypeRefBuilder:
        return self.__ref

    def build_load_json_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.mode("json").build_dto_decode_expr(scope, self.__ref, source)

    def build_model_to_domain_param_stmts(
        self,
        scope: ScopeASTBuilder,
        params: t.Mapping[str, ParameterInfo],
        source: AttrASTBuilder,
    ) -> None:
        for name, info in params.items():
            scope.assign_stmt(
                target=name,
                value=self.__mapper.build_dto_to_domain_expr(scope, info.type_, source.attr(info.name)),
            )

    def build_model_to_domain_expr(
        self,
        scope: ScopeASTBuilder,
        domain: TypeInfo,
        source: AttrASTBuilder,
    ) -> Expr:
        return self.__mapper.build_dto_to_domain_expr(scope, domain, source)

    def build_domain_to_model_expr(
        self,
        scope: ScopeASTBuilder,
        domain: TypeInfo,
        source: Expr,
    ) -> Expr:
        return scope.call(self.__ref).kwarg(
            "payload",
            self.__mapper.build_domain_to_dto_expr(scope, domain, source),
        )

    def build_dump_serializable_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.mode("serializable").build_dto_encode_expr(scope, self.__ref, source)

    def build_dump_json_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.mode("json").build_dto_encode_expr(scope, self.__ref, source)


class AiohttpModelRegistry:
    def __init__(self, mapper: PydanticDtoMapper) -> None:
        self.__mapper = mapper

        self.__requests = dict[tuple[str, str], AiohttpModel]()
        self.__responses = dict[tuple[str, str], AiohttpModel]()

    def register(self, scope: ScopeASTBuilder, entrypoint: EntrypointInfo, method: MethodInfo) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            self.__register_unary_request(scope, entrypoint, method)
            self.__register_unary_response(scope, entrypoint, method)

        elif isinstance(method, StreamStreamMethodInfo):
            self.__register_stream_request(scope, entrypoint, method)
            self.__register_stream_response(scope, entrypoint, method)

        else:
            assert_never(method)

    def get_request(self, entrypoint: EntrypointInfo, method: MethodInfo) -> AiohttpModel:
        return self.__requests[(entrypoint.name, method.name)]

    def get_response(self, entrypoint: EntrypointInfo, method: MethodInfo) -> t.Optional[AiohttpModel]:
        return self.__responses.get((entrypoint.name, method.name))

    def __register_unary_request(
        self,
        scope: ScopeASTBuilder,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        model_ref = self.__mapper.create_dto_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Request"),
            fields={param.name: param.type_ for param in method.params},
            doc=f"Request DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method.",
        )

        self.__requests[(entrypoint.name, method.name)] = AiohttpModel(
            mapper=self.__mapper,
            ref=model_ref,
        )

    def __register_unary_response(
        self,
        scope: ScopeASTBuilder,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        if method.returns is None:
            return

        model_ref = self.__mapper.create_dto_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Response"),
            fields={"payload": method.returns},
            doc=f"Response DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method.",
        )

        self.__responses[(entrypoint.name, method.name)] = AiohttpModel(
            mapper=self.__mapper,
            ref=model_ref,
        )

    def __register_stream_request(
        self,
        scope: ScopeASTBuilder,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        model_ref = self.__mapper.create_dto_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Request"),
            fields={method.input_.name: method.input_.type_},
            doc=f"Request DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method.",
        )

        self.__requests[(entrypoint.name, method.name)] = AiohttpModel(
            mapper=self.__mapper,
            ref=model_ref,
        )

    def __register_stream_response(
        self,
        scope: ScopeASTBuilder,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        if method.output is None:
            return

        model_ref = self.__mapper.create_dto_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Response"),
            fields={"payload": method.output},
            doc=f"Response DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method.",
        )

        self.__responses[(entrypoint.name, method.name)] = AiohttpModel(
            mapper=self.__mapper,
            ref=model_ref,
        )

    def __create_model_name(
        self,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
        suffix: str,
    ) -> str:
        return "".join(snake2camel(s) for s in (entrypoint.name, method.name, suffix))


class AiohttpCodeGenerator(CodeGenerator):
    def __init__(self, loader: TypeLoader, inspector: TypeInspector, annotator: TypeAnnotator) -> None:
        self.__loader = loader
        self.__inspector = inspector
        self.__annotator = annotator

    @override
    def generate(self, context: CodeGeneratorContext) -> CodeGeneratorResult:
        with self.__init_root(context) as (root, pkg):
            registry = self.__build_model_module(context, pkg)
            self.__build_server_module(context, pkg, registry)
            self.__build_client_module(context, pkg, registry)

        return CodeGeneratorResult(
            files=[
                CodeGeneratorResult.File(
                    path=context.output.joinpath(module.file),
                    content=content,
                )
                for module, content in root.render()
            ],
        )

    @contextmanager
    def __init_root(self, context: CodeGeneratorContext) -> t.Iterator[tuple[PackageASTBuilder, PackageASTBuilder]]:
        if context.package is not None:
            with package(context.package, inspector=self.__inspector) as pkg:
                yield pkg, pkg

        else:
            with package("api") as api_pkg:
                with api_pkg.init():
                    pass

                with api_pkg.sub("aiohttp") as aiohttp_pkg:
                    with aiohttp_pkg.init():
                        pass

                    yield api_pkg, aiohttp_pkg

    def __build_model_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
    ) -> AiohttpModelRegistry:
        registry = AiohttpModelRegistry(
            mapper=PydanticDtoMapper(
                loader=self.__loader,
                inspector=self.__inspector,
                annotator=self.__annotator,
            ),
        )

        with pkg.module("model") as mod:
            for entrypoint in context.entrypoints:
                for method in entrypoint.methods:
                    registry.register(mod, entrypoint, method)

        return registry

    def __build_server_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: AiohttpModelRegistry,
    ) -> None:
        with pkg.module("server") as server:
            for entrypoint in context.entrypoints:
                with server.class_def(f"{snake2camel(entrypoint.name)}Handler") as handler_def:
                    with (
                        handler_def.init_def()
                        .arg("impl", entrypoint.type_)
                        .arg("executor", handler_def.optional_type(self.__executor_type), handler_def.const(None))
                    ) as init_def:
                        for name in ["impl", "executor"]:
                            init_def.assign_stmt(
                                target=init_def.self_attr(name),
                                value=init_def.attr(name),
                            )

                    for method in entrypoint.methods:
                        self.__build_server_handler_method(handler_def, registry, entrypoint, method)

                self.__build_server_entrypoint_subapp(server, entrypoint, handler_def)

    def __build_server_handler_method(
        self,
        scope: ClassScopeASTBuilder,
        registry: AiohttpModelRegistry,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
    ) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            self.__build_server_handler_method_unary_unary(scope, registry, entrypoint, method)

        elif isinstance(method, StreamStreamMethodInfo):
            self.__build_server_handler_method_stream_stream(scope, registry, entrypoint, method)

        else:
            assert_never(method)

    def __build_server_handler_method_unary_unary(
        self,
        scope: ClassScopeASTBuilder,
        registry: AiohttpModelRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        with (
            scope.method_def(method.name)
            .arg("raw_request", self.__aiohttp_request)
            .returns(self.__aiohttp_response)
            .async_() as method_def
        ):
            scope.assign_stmt(
                "request", request_model.build_load_json_expr(scope, scope.attr("raw_request", "read").call().await_())
            )

            input_params = {f"input_{param.name}": param for param in method.params}

            request_model.build_model_to_domain_param_stmts(
                scope=method_def,
                params=input_params,
                source=scope.attr("request"),
            )

            if method.is_async:
                impl_call = (
                    method_def.self_attr("impl", method.name)
                    .call(
                        kwargs={param.name: scope.attr(input_name) for input_name, param in input_params.items()},
                    )
                    .await_()
                )

            else:
                impl_call = (
                    scope.call(self.__asyncio_get_running_loop)
                    .attr("run_in_executor")
                    .call()
                    .arg(method_def.self_attr("executor"))
                    .arg(
                        scope.call(
                            self.__functools_partial,
                            args=[method_def.self_attr("impl", method.name)],
                            kwargs={param.name: scope.attr(input_name) for input_name, param in input_params.items()},
                        )
                    )
                    .await_()
                )

            if method.returns is not None and response_model is not None:
                scope.assign_stmt("output", impl_call)
                scope.assign_stmt(
                    "response",
                    response_model.build_domain_to_model_expr(method_def, method.returns, scope.attr("output")),
                )
                scope.return_stmt(
                    scope.call(self.__aiohttp_json_response).kwarg(
                        "data", response_model.build_dump_serializable_expr(scope, scope.attr("response"))
                    )
                )

            else:
                scope.stmt(impl_call)
                scope.return_stmt(scope.call(self.__aiohttp_json_response))

    def __build_server_handler_method_stream_stream(
        self,
        scope: ClassScopeASTBuilder,
        registry: AiohttpModelRegistry,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        if not method.is_async:
            msg = "synchronous stream stream methods are not supported, make this method asynchronous"
            raise NotImplementedError(msg, method)

        if method.output is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        if response_model is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        with (
            scope.method_def(method.name)
            .arg("raw_request", self.__aiohttp_request)
            .returns(self.__aiohttp_server_ws_response)
            .async_(is_async=method.is_async) as method_def
        ):
            scope.assign_stmt(
                target="websocket",
                value=scope.call(self.__aiohttp_server_ws_response),
            )

            with (
                method_def.func_def("receive_inputs")
                .returns(scope.iterator_type(method.input_.type_, is_async=True))
                .async_()
            ):
                with scope.for_stmt("msg", scope.attr("websocket")).async_().body():
                    scope.assign_stmt(
                        target="request",
                        value=request_model.build_load_json_expr(scope, scope.attr("msg", "data")),
                    )
                    scope.yield_stmt(
                        request_model.build_model_to_domain_expr(
                            method_def,
                            method.input_.type_,
                            scope.attr("request", method.input_.name),
                        ),
                    )

            scope.stmt(scope.attr("websocket", "prepare").call().arg(scope.attr("raw_request")).await_())

            with (
                scope.for_stmt(
                    target="output",
                    items=method_def.self_attr("impl", method.name).call().arg(scope.attr("receive_inputs").call()),
                )
                .async_()
                .body()
            ):
                scope.assign_stmt(
                    target="response",
                    value=response_model.build_domain_to_model_expr(
                        method_def,
                        method.output,
                        scope.attr("output"),
                    ),
                )
                scope.stmt(
                    scope.attr("websocket", "send_str")
                    .call()
                    .arg(response_model.build_dump_json_expr(scope, scope.attr("response")))
                    .await_(),
                )

            scope.return_stmt(scope.attr("websocket"))

    def __build_server_entrypoint_subapp(
        self,
        scope: ModuleASTBuilder,
        entrypoint: EntrypointInfo,
        handler_def: TypeRef,
    ) -> None:
        with (
            scope.func_def(f"add_{camel2snake(entrypoint.name)}_subapp")
            .arg("app", self.__aiohttp_web_app)
            .arg("handler", handler_def)
            .returns(scope.none())
        ):
            scope.assign_stmt("sub", scope.call(self.__aiohttp_web_app))

            for method in entrypoint.methods:
                if isinstance(method, UnaryUnaryMethodInfo):
                    scope.stmt(
                        scope.attr("sub", "router", "add_post")
                        .call()
                        .kwarg("path", scope.const(f"/{method.name}"))
                        .kwarg("handler", scope.attr("handler", method.name)),
                    )

                elif isinstance(method, StreamStreamMethodInfo):
                    scope.stmt(
                        scope.attr("sub", "router", "add_get")
                        .call()
                        .kwarg("path", scope.const(f"/{method.name}"))
                        .kwarg("handler", scope.attr("handler", method.name)),
                    )

                else:
                    assert_never(method)

            scope.stmt(
                scope.attr("app", "add_subapp")
                .call()
                .kwarg("prefix", scope.const(f"/{camel2snake(entrypoint.name)}"))
                .kwarg("subapp", scope.attr("sub"))
            )

    def __build_client_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: AiohttpModelRegistry,
    ) -> None:
        with pkg.module("client") as client:
            for entrypoint in context.entrypoints:
                with client.class_def(f"{snake2camel(entrypoint.name)}Client") as client_class:
                    with client_class.init_self_attrs_def({"session": self.__aiohttp_client_session}):
                        pass

                    for method in entrypoint.methods:
                        if isinstance(method, UnaryUnaryMethodInfo):
                            self.__build_client_method_unary_unary(client_class, registry, entrypoint, method)

                        elif isinstance(method, StreamStreamMethodInfo):
                            self.__build_client_method_stream_stream(client_class, registry, entrypoint, method)

                        else:
                            assert_never(method)

    def __build_client_method_unary_unary(
        self,
        scope: ClassScopeASTBuilder,
        registry: AiohttpModelRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        with (
            scope.method_def(method.name)
            .arg("request", request_model)
            .returns(response_model if response_model is not None else scope.const(None))
            .async_() as method_def
        ):
            with (
                scope.with_stmt()
                .async_()
                .enter(
                    cm=method_def.self_attr("session", "post")
                    .call()
                    .kwarg("url", scope.const(f"/{camel2snake(entrypoint.name)}/{method.name}"))
                    .kwarg("json", request_model.build_dump_serializable_expr(scope, scope.attr("request"))),
                    name="raw_response",
                )
                .body()
            ):
                if method.returns is not None and response_model is not None:
                    scope.assign_stmt(
                        target="response",
                        value=response_model.build_load_json_expr(
                            scope,
                            scope.attr("raw_response", "read").call().await_(),
                        ),
                    )
                    scope.return_stmt(scope.attr("response"))

    def __build_client_method_stream_stream(
        self,
        scope: ClassScopeASTBuilder,
        registry: AiohttpModelRegistry,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        if method.output is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        if response_model is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        with (
            scope.method_def(method.name)
            .arg("requests", request_model.ref().iterator(is_async=True))
            .returns(response_model.ref().iterator(is_async=True))
            .async_() as method_def
        ):
            with (
                scope.func_def("send_requests")
                .arg("ws", self.__aiohttp_client_ws_response)
                .returns(scope.none())
                .async_()
            ):
                with scope.try_stmt() as try_stmt:
                    with try_stmt.body():
                        with scope.for_stmt("request", scope.attr("requests")).async_().body():
                            scope.stmt(
                                scope.attr("ws", "send_json")
                                .call()
                                .arg(request_model.build_dump_serializable_expr(scope, scope.attr("request")))
                                .await_(),
                            )

                    with try_stmt.finally_():
                        scope.stmt(scope.attr("ws", "close").call().await_())

            with (
                scope.with_stmt()
                .async_()
                .enter(
                    cm=method_def.self_attr("session", "ws_connect")
                    .call()
                    .kwarg("url", scope.const(f"/{camel2snake(entrypoint.name)}/{method.name}")),
                    name="ws",
                )
                .body()
            ):
                scope.assign_stmt(
                    target="sender",
                    value=scope.call(self.__asyncio_create_task).arg(
                        scope.attr("send_requests").call().arg(scope.attr("ws"))
                    ),
                )
                with scope.try_stmt() as try_stream:
                    with try_stream.body():
                        with scope.while_stmt(scope.not_op(scope.attr("ws", "closed"))).body():
                            scope.assign_stmt(
                                target="msg",
                                value=scope.attr("ws", "receive").call().await_(),
                            )

                            with scope.if_stmt(scope.attr("ws", "closed")).body():
                                scope.break_stmt()

                            with scope.if_stmt(
                                scope.compare_in_expr(
                                    scope.attr("msg", "type"),
                                    scope.set_expr(
                                        [
                                            scope.attr(self.__aiohttp_ws_msg_type, "CLOSING"),
                                            scope.attr(self.__aiohttp_ws_msg_type, "CLOSED"),
                                            scope.attr(self.__aiohttp_ws_msg_type, "CLOSE"),
                                        ]
                                    ),
                                )
                            ).body():
                                scope.continue_stmt()

                            with scope.if_stmt(
                                scope.compare_is_expr(
                                    scope.attr("msg", "type"),
                                    scope.attr(self.__aiohttp_ws_msg_type, "ERROR"),
                                )
                            ).body():
                                scope.raise_stmt(scope.attr("msg", "data"))

                            scope.assign_stmt(
                                target="response",
                                value=response_model.build_load_json_expr(scope, scope.attr("msg", "data")),
                            )
                            scope.yield_stmt(scope.attr("response"))

                    with try_stream.finally_():
                        scope.stmt(scope.attr("sender").await_())

    @cached_property
    def __functools_partial(self) -> TypeInfo:
        return NamedTypeInfo.build("functools", "partial")

    @cached_property
    def __executor_type(self) -> TypeInfo:
        return NamedTypeInfo.build(ModuleInfo.build("concurrent", "futures"), "Executor")

    @cached_property
    def __asyncio_create_task(self) -> TypeInfo:
        return NamedTypeInfo.build("asyncio", "create_task")

    @cached_property
    def __asyncio_get_running_loop(self) -> TypeInfo:
        return NamedTypeInfo.build("asyncio", "get_running_loop")

    @cached_property
    def __aiohttp_web(self) -> ModuleInfo:
        return ModuleInfo.build("aiohttp", "web")

    @cached_property
    def __aiohttp_web_app(self) -> NamedTypeInfo:
        return NamedTypeInfo.build(self.__aiohttp_web, "Application")

    @cached_property
    def __aiohttp_client_session(self) -> TypeInfo:
        return NamedTypeInfo.build("aiohttp", "ClientSession")

    @cached_property
    def __aiohttp_server_ws_response(self) -> NamedTypeInfo:
        return NamedTypeInfo.build(self.__aiohttp_web, "WebSocketResponse")

    @cached_property
    def __aiohttp_client_ws_response(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("aiohttp", "ClientWebSocketResponse")

    @cached_property
    def __aiohttp_ws_msg_type(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("aiohttp", "WSMsgType")

    @cached_property
    def __aiohttp_request(self) -> TypeInfo:
        return NamedTypeInfo.build(self.__aiohttp_web, "Request")

    @cached_property
    def __aiohttp_response(self) -> TypeInfo:
        return NamedTypeInfo.build(self.__aiohttp_web, "Response")

    @cached_property
    def __aiohttp_json_response(self) -> TypeInfo:
        return NamedTypeInfo.build(self.__aiohttp_web, "json_response")
