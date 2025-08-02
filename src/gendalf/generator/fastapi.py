import typing as t
from contextlib import contextmanager
from functools import cached_property

from astlab import package
from astlab.abc import Expr, TypeDefinitionBuilder, TypeRef
from astlab.builder import (
    AttrASTBuilder,
    ClassScopeASTBuilder,
    ClassTypeRefBuilder,
    MethodScopeASTBuilder,
    ModuleASTBuilder,
    PackageASTBuilder,
    ScopeASTBuilder,
)
from astlab.types import NamedTypeInfo, TypeAnnotator, TypeInfo, TypeInspector, TypeLoader

from gendalf._typing import assert_never, override
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.dto.pydantic import PydanticDtoMapper
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult
from gendalf.model import EntrypointInfo, MethodInfo, ParameterInfo, StreamStreamMethodInfo, UnaryUnaryMethodInfo
from gendalf.string_case import camel2snake, snake2camel


class FastAPIModel(TypeDefinitionBuilder):
    def __init__(self, mapper: PydanticDtoMapper, ref: ClassTypeRefBuilder) -> None:
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

    def build_model_to_domain_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: AttrASTBuilder) -> Expr:
        return self.__mapper.build_dto_to_domain_expr(scope, domain, source)

    def build_domain_to_model_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        return scope.call(self.__ref).kwarg(
            "payload",
            self.__mapper.build_domain_to_dto_expr(scope, domain, source),
        )

    def build_dump_json_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.mode("json").build_dto_encode_expr(scope, self.__ref, source)

    def build_dump_serializable_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.mode("serializable").build_dto_encode_expr(scope, self.__ref, source)


class FastAPIModelRegistry:
    def __init__(self, mapper: PydanticDtoMapper) -> None:
        self.__mapper = mapper

        self.__requests = dict[tuple[str, str], FastAPIModel]()
        self.__responses = dict[tuple[str, str], FastAPIModel]()

    def register(self, scope: ScopeASTBuilder, entrypoint: EntrypointInfo, method: MethodInfo) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            self.__register_unary_request(scope, entrypoint, method)
            self.__register_unary_response(scope, entrypoint, method)

        elif isinstance(method, StreamStreamMethodInfo):
            self.__register_stream_request(scope, entrypoint, method)
            self.__register_stream_response(scope, entrypoint, method)

        else:
            assert_never(method)

    def get_request(self, entrypoint: EntrypointInfo, method: MethodInfo) -> FastAPIModel:
        return self.__requests[(entrypoint.name, method.name)]

    def get_response(self, entrypoint: EntrypointInfo, method: MethodInfo) -> t.Optional[FastAPIModel]:
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

        self.__requests[(entrypoint.name, method.name)] = FastAPIModel(
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

        self.__responses[(entrypoint.name, method.name)] = FastAPIModel(
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

        self.__requests[(entrypoint.name, method.name)] = FastAPIModel(
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

        self.__responses[(entrypoint.name, method.name)] = FastAPIModel(
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


class FastAPICodeGenerator(CodeGenerator):
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

                with api_pkg.sub("fastapi") as fastapi_pkg:
                    with fastapi_pkg.init():
                        pass

                    yield api_pkg, fastapi_pkg

    def __build_model_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
    ) -> FastAPIModelRegistry:
        registry = FastAPIModelRegistry(
            mapper=PydanticDtoMapper(
                mode="python",
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
        registry: FastAPIModelRegistry,
    ) -> None:
        with pkg.module("server") as server:
            for entrypoint in context.entrypoints:
                with server.class_def(f"{snake2camel(entrypoint.name)}Handler") as handler_def:
                    with handler_def.init_self_attrs_def({"impl": entrypoint.type_}):
                        pass

                    for method in entrypoint.methods:
                        self.__build_server_handler_method(handler_def, registry, entrypoint, method)

                self.__build_server_entrypoint_router(server, entrypoint, handler_def)

    def __build_server_router_method(self, scope: ScopeASTBuilder, method: MethodInfo) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            scope.stmt(
                scope.attr("router", "post")
                .call()
                .kwarg("path", scope.const(f"/{method.name}"))
                .kwarg("description", scope.const(method.doc) if method.doc is not None else scope.none())
                .call()
                .arg(scope.attr("handler", method.name)),
            )

        elif isinstance(method, StreamStreamMethodInfo):
            scope.stmt(
                scope.attr("router", "websocket")
                .call()
                .kwarg("path", scope.const(f"/{method.name}"))
                .call()
                .arg(scope.attr("handler", method.name)),
            )

        else:
            assert_never(method)

    def __build_server_handler_method(
        self,
        scope: ClassScopeASTBuilder,
        registry: FastAPIModelRegistry,
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
        registry: FastAPIModelRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        with (
            scope.method_def(method.name)
            .arg("request", request_model)
            .returns(response_model if response_model is not None else scope.none())
            .async_(is_async=method.is_async) as method_def
        ):
            input_params = {f"input_{param.name}": param for param in method.params}

            request_model.build_model_to_domain_param_stmts(
                scope=method_def,
                params=input_params,
                source=scope.attr("request"),
            )

            impl_call = (
                method_def.self_attr("impl", method.name)
                .call(
                    kwargs={param.name: scope.attr(input_name) for input_name, param in input_params.items()},
                )
                .await_(is_awaited=method.is_async)
            )

            if method.returns is not None and response_model is not None:
                scope.assign_stmt("output", impl_call)
                scope.assign_stmt(
                    "response",
                    response_model.build_domain_to_model_expr(method_def, method.returns, scope.attr("output")),
                )
                scope.return_stmt(scope.attr("response"))

            else:
                scope.stmt(impl_call)

    def __build_server_handler_method_stream_stream(
        self,
        scope: ClassScopeASTBuilder,
        registry: FastAPIModelRegistry,
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
            .arg("websocket", NamedTypeInfo.build("fastapi", "WebSocket"))
            .returns(scope.none())
            .async_(is_async=method.is_async) as method_def
        ):
            with (
                method_def.func_def("receive_inputs")
                .returns(scope.iterator_type(method.input_.type_, is_async=True))
                .async_()
            ):
                with scope.for_stmt("request_text", scope.attr("websocket", "iter_text").call()).async_().body():
                    scope.assign_stmt(
                        target="request",
                        value=request_model.build_load_json_expr(scope, scope.attr("request_text")),
                    )
                    scope.yield_stmt(
                        request_model.build_model_to_domain_expr(
                            method_def,
                            method.input_.type_,
                            scope.attr("request", method.input_.name),
                        ),
                    )

            with scope.try_stmt() as try_stmt:
                with try_stmt.body():
                    scope.stmt(scope.attr("websocket", "accept").call().await_())

                    with (
                        scope.for_stmt(
                            target="output",
                            items=method_def.self_attr("impl", method.name)
                            .call()
                            .arg(scope.attr("receive_inputs").call()),
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
                            scope.attr("websocket", "send_text")
                            .call()
                            .arg(response_model.build_dump_json_expr(scope, scope.attr("response")))
                            .await_(),
                        )

                with try_stmt.except_(NamedTypeInfo.build("fastapi", "WebSocketDisconnect")):
                    pass

    def __build_server_entrypoint_router(
        self,
        scope: ModuleASTBuilder,
        entrypoint: EntrypointInfo,
        handler_def: TypeRef,
    ) -> None:
        fastapi_router_ref = NamedTypeInfo.build("fastapi", "APIRouter")

        with (
            scope.func_def(f"create_{camel2snake(entrypoint.name)}_router")
            .arg("handler", handler_def)
            .returns(fastapi_router_ref)
        ):
            scope.assign_stmt(
                "router",
                value=scope.call(fastapi_router_ref)
                .kwarg("prefix", scope.const(f"/{camel2snake(entrypoint.name)}"))
                .kwarg("tags", scope.list_expr([scope.const(entrypoint.name)])),
            )

            for method in entrypoint.methods:
                self.__build_server_router_method(scope, method)

            scope.return_stmt(scope.attr("router"))

    def __build_client_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: FastAPIModelRegistry,
    ) -> None:
        with pkg.module("client") as client:
            for entrypoint in context.entrypoints:
                with client.class_def(f"{snake2camel(entrypoint.name)}Client") as client_class:
                    with client_class.init_self_attrs_def({"impl": NamedTypeInfo.build("httpx", "Client")}):
                        pass

                    for method in entrypoint.methods:
                        self.__build_client_method(client_class, registry, entrypoint, method, is_async=False)

                with client.class_def(f"{snake2camel(entrypoint.name)}AsyncClient") as async_client_class:
                    with async_client_class.init_self_attrs_def({"impl": NamedTypeInfo.build("httpx", "AsyncClient")}):
                        pass

                    for method in entrypoint.methods:
                        self.__build_client_method(async_client_class, registry, entrypoint, method, is_async=True)

    def __build_client_method(
        self,
        scope: ClassScopeASTBuilder,
        registry: FastAPIModelRegistry,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
        *,
        is_async: bool,
    ) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            self.__build_client_method_unary_unary(scope, registry, entrypoint, method, is_async=is_async)

        elif isinstance(method, StreamStreamMethodInfo):
            self.__build_client_method_stream_stream(scope, registry, entrypoint, method, is_async=is_async)

        else:
            assert_never(method)

    def __build_client_method_unary_unary(
        self,
        scope: ClassScopeASTBuilder,
        registry: FastAPIModelRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
        *,
        is_async: bool,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        with (
            scope.method_def(method.name)
            .arg("request", request_model)
            .returns(response_model if response_model is not None else scope.const(None))
            .async_(is_async=is_async) as method_def
        ):
            request_call_expr = (
                method_def.self_attr("impl", "post")
                .call()
                .kwarg("url", scope.const(f"/{camel2snake(entrypoint.name)}/{method.name}"))
                .kwarg("json", request_model.build_dump_serializable_expr(scope, scope.attr("request")))
                .await_(is_awaited=is_async)
            )

            if method.returns is not None and response_model is not None:
                scope.assign_stmt("raw_response", request_call_expr)
                scope.assign_stmt(
                    target="response",
                    value=response_model.build_load_json_expr(scope, scope.attr("raw_response", "read").call()),
                )
                scope.return_stmt(scope.attr("response"))

            else:
                scope.stmt(request_call_expr)

    def __build_client_method_stream_stream(
        self,
        scope: ClassScopeASTBuilder,
        registry: FastAPIModelRegistry,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
        *,
        is_async: bool,
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
            .arg("requests", request_model.ref().iterator(is_async=is_async))
            .arg("receive_timeout", scope.type_ref(float).optional(), scope.const(None))
            .returns(response_model.ref().iterator(is_async=is_async))
            .async_(is_async=is_async) as method_def
        ):
            url = scope.const(f"/{camel2snake(entrypoint.name)}/{method.name}")

            if is_async:
                self.__build_client_method_stream_stream_async(method_def, request_model, response_model, url)

            else:
                self.__build_client_method_stream_stream_sync(method_def, request_model, response_model, url)

    def __build_client_method_stream_stream_async(
        self,
        scope: MethodScopeASTBuilder,
        request_model: FastAPIModel,
        response_model: FastAPIModel,
        url: Expr,
    ) -> None:
        with scope.func_def("send_requests").arg("ws", self.__ws_async_session).returns(scope.none()).async_():
            with scope.try_stmt() as try_receive_once:
                with try_receive_once.body():
                    with scope.for_stmt("request", scope.attr("requests")).async_().body():
                        scope.stmt(
                            scope.attr("ws", "send_text")
                            .call()
                            .arg(request_model.build_dump_json_expr(scope, scope.attr("request")))
                            .await_(),
                        )

                with try_receive_once.finally_():
                    scope.stmt(scope.attr("ws", "close").call().await_())

        with (
            scope.with_stmt()
            .async_()
            .enter(scope.call(self.__ws_async_connect).kwarg("url", url).kwarg("client", scope.self_attr("impl")), "ws")
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
                    with scope.while_stmt(scope.not_op(scope.attr("sender", "done").call())).body():
                        with scope.try_stmt() as try_receive_once:
                            with try_receive_once.body():
                                scope.assign_stmt(
                                    target="raw_response",
                                    value=scope.attr("ws", "receive_text")
                                    .call()
                                    .kwarg("timeout", scope.attr("receive_timeout"))
                                    .await_(),
                                )

                            with try_receive_once.except_(*self.__ws_receiver_no_data_errors):
                                scope.continue_stmt()

                            with try_receive_once.except_(*self.__ws_receiver_network_errors, name="err"):
                                with scope.if_stmt(scope.attr("sender", "done").call()).body():
                                    scope.break_stmt()

                                scope.raise_stmt(scope.attr("err"))

                            with try_receive_once.else_():
                                scope.assign_stmt(
                                    target="response",
                                    value=response_model.build_load_json_expr(scope, scope.attr("raw_response")),
                                )
                                scope.yield_stmt(scope.attr("response"))

                with try_stream.finally_():
                    scope.stmt(scope.attr("sender").await_())

    def __build_client_method_stream_stream_sync(
        self,
        scope: MethodScopeASTBuilder,
        request_model: FastAPIModel,
        response_model: FastAPIModel,
        url: Expr,
    ) -> None:
        scope.assign_stmt("done", scope.attr("threading", "Event").call())

        with scope.func_def("send_requests").arg("ws", self.__ws_sync_session).returns(scope.none()):
            scope.stmt(scope.attr("done", "clear").call())
            with scope.try_stmt() as try_stmt:
                with try_stmt.body():
                    with scope.for_stmt("request", scope.attr("requests")).body():
                        scope.stmt(
                            scope.attr("ws", "send_text")
                            .call()
                            .arg(request_model.build_dump_json_expr(scope, scope.attr("request")))
                        )

                with try_stmt.finally_():
                    scope.stmt(scope.attr("done", "set").call())
                    scope.stmt(scope.attr("ws", "close").call())

        with (
            scope.with_stmt()
            .enter(scope.call(self.__ws_sync_connect).kwarg("url", url).kwarg("client", scope.self_attr("impl")), "ws")
            .body()
        ):
            scope.assign_stmt(
                target="sender",
                value=scope.call(self.__threading_thread)
                .kwarg("target", scope.attr("send_requests"))
                .kwarg("args", scope.tuple_expr(scope.attr("ws")))
                .kwarg("daemon", scope.const(value=True)),
            )
            scope.stmt(scope.attr("sender", "start").call())

            with scope.while_stmt(scope.not_op(scope.attr("done", "is_set").call())).body():
                with scope.try_stmt() as try_stmt:
                    with try_stmt.body():
                        scope.assign_stmt(
                            target="raw_response",
                            value=scope.attr("ws", "receive_text")
                            .call()
                            .kwarg("timeout", scope.attr("receive_timeout")),
                        )

                    with try_stmt.except_(*self.__ws_receiver_no_data_errors):
                        scope.continue_stmt()

                    with try_stmt.except_(*self.__ws_receiver_network_errors, name="err"):
                        with scope.if_stmt(scope.attr("done", "is_set").call()).body():
                            scope.break_stmt()

                        scope.raise_stmt(scope.attr("err"))

                    with try_stmt.else_():
                        scope.assign_stmt(
                            target="response",
                            value=response_model.build_load_json_expr(scope, scope.attr("raw_response")),
                        )
                        scope.yield_stmt(scope.attr("response"))

    @cached_property
    def __threading_thread(self) -> TypeInfo:
        return NamedTypeInfo.build("threading", "Thread")

    @cached_property
    def __asyncio_create_task(self) -> TypeInfo:
        return NamedTypeInfo.build("asyncio", "create_task")

    @cached_property
    def __ws_sync_connect(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("httpx_ws", "connect_ws")

    @cached_property
    def __ws_async_connect(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("httpx_ws", "aconnect_ws")

    @cached_property
    def __ws_sync_session(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("httpx_ws", "WebSocketSession")

    @cached_property
    def __ws_async_session(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("httpx_ws", "AsyncWebSocketSession")

    @cached_property
    def __ws_receiver_no_data_errors(self) -> t.Sequence[TypeInfo]:
        return [NamedTypeInfo.build("queue", "Empty")]

    @cached_property
    def __ws_receiver_network_errors(self) -> t.Sequence[TypeInfo]:
        return [
            NamedTypeInfo.build("httpx_ws", "WebSocketNetworkError"),
            NamedTypeInfo.build("httpx_ws", "WebSocketDisconnect"),
        ]
