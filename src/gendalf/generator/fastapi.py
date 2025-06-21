import typing as t

from astlab import package
from astlab.abc import Expr, TypeDefinitionBuilder, TypeRef
from astlab.builder import (
    AttrASTBuilder,
    ClassBodyASTBuilder,
    ClassRefBuilder,
    ModuleASTBuilder,
    PackageASTBuilder,
    ScopeASTBuilder,
)
from astlab.types import NamedTypeInfo, TypeInfo, TypeInspector, TypeLoader

from gendalf._typing import assert_never, override
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.dto.pydantic import PydanticDtoMapper
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult
from gendalf.model import EntrypointInfo, MethodInfo, ParameterInfo, StreamStreamMethodInfo, UnaryUnaryMethodInfo
from gendalf.string_case import camel2snake, snake2camel


class FastAPIModel(TypeDefinitionBuilder):
    def __init__(
        self,
        mapper: PydanticDtoMapper,
        ref: ClassRefBuilder,
    ) -> None:
        self.__mapper = mapper
        self.__ref = ref

    @override
    @property
    def info(self) -> TypeInfo:
        return self.__ref.info

    @override
    def ref(self) -> ClassRefBuilder:
        return self.__ref

    def build_load_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.build_dto_decode_expr(scope, self.__ref, source)

    def build_model_to_domain_param_stmts(
        self,
        scope: ScopeASTBuilder,
        params: t.Mapping[str, ParameterInfo],
        source: AttrASTBuilder,
    ) -> None:
        for name, info in params.items():
            scope.assign_stmt(
                target=name,
                value=self.__mapper.build_dto_to_domain_expr(scope, self.__ref, info.type_, source.attr(info.name)),
            )

    def build_model_to_domain_expr(
        self,
        scope: ScopeASTBuilder,
        domain: TypeRef,
        source: AttrASTBuilder,
    ) -> Expr:
        return self.__mapper.build_dto_to_domain_expr(scope, self.__ref, domain, source)

    def build_domain_to_model_expr(
        self,
        scope: ScopeASTBuilder,
        domain: TypeInfo,
        source: Expr,
    ) -> Expr:
        return scope.call(self.__ref).kwarg(
            "payload",
            self.__mapper.build_domain_to_dto_expr(scope, domain, self.__ref, source),
        )

    def build_dump_expr(self, scope: ScopeASTBuilder, source: Expr) -> Expr:
        return self.__mapper.build_dto_encode_expr(scope, self.__ref, source)


class FastAPIDtoRegistry:
    def __init__(self, mapper: PydanticDtoMapper) -> None:
        self.__mapper = mapper

        self.__requests = dict[tuple[str, str], FastAPIModel]()
        self.__responses = dict[tuple[str, str], FastAPIModel]()

    def register(self, scope: ScopeASTBuilder, entrypoint: EntrypointInfo, method: MethodInfo) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            self.__register_unary_request(scope, entrypoint, method)

            if method.returns is not None:
                self.__register_unary_response(scope, entrypoint, method)

        elif isinstance(method, StreamStreamMethodInfo):
            self.__register_stream_request(scope, entrypoint, method)

            if method.output is not None:
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
        model_ref = self.__mapper.create_dto_class_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Request"),
            fields={param.name: param.type_ for param in method.params},
            doc=f"Request DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method",
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

        model_ref = self.__mapper.create_dto_class_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Response"),
            fields={"payload": method.returns},
            doc=f"Response DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method",
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
        model_ref = self.__mapper.create_dto_class_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Request"),
            fields={method.input_.name: method.input_.type_},
            doc=f"Request DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method",
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

        model_ref = self.__mapper.create_dto_class_def(
            scope=scope,
            name=self.__create_model_name(entrypoint, method, "Response"),
            fields={"payload": method.output},
            doc=f"Response DTO for :class:`{entrypoint.type_.qualname}` :meth:`{method.name}` entrypoint method",
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
    def __init__(self, inspector: TypeInspector, loader: TypeLoader) -> None:
        self.__inspector = inspector
        self.__loader = loader

    @override
    def generate(self, context: CodeGeneratorContext) -> CodeGeneratorResult:
        with package(context.package or "api", inspector=self.__inspector) as pkg:
            with pkg.init():
                pass

            registry = self.__build_model_module(context, pkg)
            self.__build_server_module(context, pkg, registry)
            self.__build_client_module(context, pkg, registry)

        return CodeGeneratorResult(
            files=[
                CodeGeneratorResult.File(
                    path=context.output.joinpath(module.file),
                    content=content,
                )
                for module, content in pkg.render()
            ],
        )

    def __build_model_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
    ) -> FastAPIDtoRegistry:
        registry = FastAPIDtoRegistry(PydanticDtoMapper(loader=self.__loader))

        with pkg.module("model") as mod:
            for entrypoint in context.entrypoints:
                for method in entrypoint.methods:
                    registry.register(mod, entrypoint, method)

        return registry

    def __build_server_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: FastAPIDtoRegistry,
    ) -> None:
        with pkg.module("server") as server:
            for entrypoint in context.entrypoints:
                with server.class_def(f"{snake2camel(entrypoint.name)}Handler") as handler_def:
                    with handler_def.init_self_attrs_def({"impl": entrypoint.type_}):
                        pass

                    for method in entrypoint.methods:
                        self.__build_server_handler_method(handler_def, registry, entrypoint, method)

                self.__build_server_entrypoint_router(server, entrypoint, handler_def)

    def __build_server_router_method(self, builder: ScopeASTBuilder, method: MethodInfo) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            builder.stmt(
                builder.attr("router", "post")
                .call()
                .kwarg("path", builder.const(f"/{method.name}"))
                .kwarg("description", builder.const(method.doc) if method.doc is not None else builder.none())
                .call()
                .arg(builder.attr("entrypoint", method.name))
            )

        elif isinstance(method, StreamStreamMethodInfo):
            builder.stmt(
                builder.attr("router", "websocket")
                .call()
                .kwarg("path", builder.const(f"/{method.name}"))
                .call()
                .arg(builder.attr("entrypoint", method.name))
            )

        else:
            assert_never(method)

    def __build_server_handler_method(
        self,
        builder: ClassBodyASTBuilder,
        registry: FastAPIDtoRegistry,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
    ) -> None:
        if isinstance(method, UnaryUnaryMethodInfo):
            self.__build_server_handler_method_unary_unary(builder, registry, entrypoint, method)

        elif isinstance(method, StreamStreamMethodInfo):
            self.__build_server_handler_method_stream_stream(builder, registry, entrypoint, method)

        else:
            assert_never(method)

    def __build_server_handler_method_unary_unary(
        self,
        builder: ClassBodyASTBuilder,
        registry: FastAPIDtoRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        with (
            builder.method_def(method.name)
            .arg("request", request_model)
            .returns(response_model if response_model is not None else builder.none())
            .async_() as method_def
        ):
            input_params = {f"input_{param.name}": param for param in method.params}

            request_model.build_model_to_domain_param_stmts(
                scope=method_def,
                params=input_params,
                source=builder.attr("request"),
            )

            impl_call = method_def.self_attr("impl", method.name).call(
                kwargs={param.name: builder.attr(input_name) for input_name, param in input_params.items()}
            )

            if method.returns is not None and response_model is not None:
                builder.assign_stmt("output", impl_call)
                builder.assign_stmt(
                    "response",
                    response_model.build_domain_to_model_expr(method_def, method.returns, builder.attr("output")),
                )
                builder.return_stmt(builder.attr("response"))

            else:
                builder.stmt(impl_call)

    def __build_server_handler_method_stream_stream(
        self,
        builder: ClassBodyASTBuilder,
        registry: FastAPIDtoRegistry,
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
            builder.method_def(method.name)
            .arg("websocket", NamedTypeInfo.build("fastapi", "WebSocket"))
            .returns(builder.none())
            .async_() as method_def
        ):
            with (
                method_def.func_def("receive_inputs")
                .returns(builder.iterator_type(method.input_.type_, is_async=True))
                .async_()
            ):
                with builder.for_stmt("request_text", builder.attr("websocket", "iter_text").call()).async_():
                    builder.assign_stmt(
                        target="request",
                        value=request_model.build_load_expr(builder, builder.attr("request_text")),
                    )
                    builder.yield_stmt(
                        request_model.build_model_to_domain_expr(
                            method_def, method.input_.type_, builder.attr("request")
                        )
                    )

            with builder.try_stmt() as try_stmt:
                with try_stmt.body():
                    builder.stmt(builder.attr("websocket", "accept").call().await_())

                    with builder.for_stmt(
                        target="output",
                        items=method_def.self_attr("impl", method.name)
                        .call()
                        .arg(builder.attr("receive_inputs").call()),
                    ).async_():
                        builder.assign_stmt(
                            target="response",
                            value=response_model.build_domain_to_model_expr(
                                method_def, method.output, builder.attr("output")
                            ),
                        )
                        builder.stmt(
                            builder.attr("websocket", "send_text")
                            .call()
                            .arg(response_model.build_dump_expr(builder, builder.attr("response")))
                            .await_()
                        )

                with try_stmt.except_(NamedTypeInfo.build("fastapi", "WebSocketDisconnect")):
                    pass

    def __build_server_entrypoint_router(
        self,
        builder: ModuleASTBuilder,
        entrypoint: EntrypointInfo,
        handler_def: TypeRef,
    ) -> None:
        fastapi_router_ref = NamedTypeInfo.build("fastapi", "APIRouter")

        with (
            builder.func_def(f"create_{camel2snake(entrypoint.name)}_router")
            .arg("entrypoint", handler_def)
            .returns(fastapi_router_ref)
        ):
            builder.assign_stmt(
                "router",
                value=builder.call(fastapi_router_ref)
                .kwarg("prefix", builder.const(f"/{camel2snake(entrypoint.name)}"))
                .kwarg("tags", builder.const([entrypoint.name])),
            )

            for method in entrypoint.methods:
                self.__build_server_router_method(builder, method)

            builder.return_stmt(builder.attr("router"))

    def __build_client_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: FastAPIDtoRegistry,
    ) -> None:
        client_impl_ref = NamedTypeInfo.build("httpx", "AsyncClient")

        with pkg.module("client") as client:
            for entrypoint in context.entrypoints:
                with client.class_def(f"{snake2camel(entrypoint.name)}AsyncClient") as client_class:
                    with client_class.init_self_attrs_def({"impl": client_impl_ref}):
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
        builder: ClassBodyASTBuilder,
        registry: FastAPIDtoRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        with (
            builder.method_def(method.name)
            .arg("request", request_model)
            .returns(response_model if response_model is not None else builder.const(None))
            .async_() as method_def
        ):
            request_call_expr = (
                method_def.self_attr("impl", "post")
                .call()
                .kwarg("url", builder.const(f"/{camel2snake(entrypoint.name)}/{method.name}"))
                .kwarg("json", request_model.build_dump_expr(builder, builder.attr("request")))
                .await_()
            )

            if method.returns is not None and response_model is not None:
                builder.assign_stmt("raw_response", request_call_expr)
                builder.assign_stmt(
                    target="response",
                    value=response_model.build_load_expr(builder, builder.attr("raw_response", "read").call()),
                )
                builder.return_stmt(builder.attr("response"))

            else:
                builder.stmt(request_call_expr)

    def __build_client_method_stream_stream(
        self,
        builder: ClassBodyASTBuilder,
        registry: FastAPIDtoRegistry,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        ws_connect_ref = NamedTypeInfo.build("httpx_ws", "aconnect_ws")
        ws_session_ref = NamedTypeInfo.build("httpx_ws", "AsyncWebSocketSession")
        ws_error_refs = [
            NamedTypeInfo.build("httpx_ws", "WebSocketNetworkError"),
            NamedTypeInfo.build("httpx_ws", "WebSocketDisconnect"),
        ]
        task_group_ref = NamedTypeInfo.build("asyncio", "TaskGroup")

        request_model = registry.get_request(entrypoint, method)
        response_model = registry.get_response(entrypoint, method)

        if method.output is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        if response_model is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        with (
            builder.method_def(method.name)
            .arg("requests", request_model.ref().iterator(is_async=True))
            .returns(response_model.ref().iterator(is_async=True))
            .async_() as method_def
        ):
            with builder.func_def("send_requests").arg("ws", ws_session_ref).returns(builder.none()).async_():
                with builder.try_stmt() as try_stmt:
                    with try_stmt.body():
                        with builder.for_stmt("request", builder.attr("requests")).async_():
                            builder.stmt(
                                builder.attr("ws", "send_text")
                                .call()
                                .arg(request_model.build_dump_expr(builder, builder.attr("request")))
                                .await_()
                            )

                    with try_stmt.finally_():
                        builder.stmt(builder.attr("ws", "close").call().await_())

            with (
                builder.with_stmt()
                .async_()
                .enter(
                    cm=builder.call(ws_connect_ref)
                    .kwarg("url", builder.const(f"/{camel2snake(entrypoint.name)}/{method.name}"))
                    .kwarg("client", method_def.self_attr("impl")),
                    name="ws",
                )
                .enter(builder.call(task_group_ref), "tasks")
            ):
                builder.assign_stmt(
                    target="sender",
                    value=builder.attr("tasks", "create_task")
                    .call()
                    .arg(builder.attr("send_requests").call().arg(builder.attr("ws"))),
                )

                with builder.while_stmt(builder.not_op(builder.attr("sender", "done").call())):
                    with builder.try_stmt() as try_stmt:
                        with try_stmt.body():
                            builder.assign_stmt(
                                target="raw_response",
                                value=builder.attr("ws", "receive_text").call().await_(),
                            )

                        with try_stmt.except_(*ws_error_refs, name="err"):
                            with builder.if_stmt(builder.attr("sender", "done").call()) as if_stmt, if_stmt.body():
                                builder.break_stmt()

                            builder.raise_stmt(builder.attr("err"))

                        with try_stmt.else_():
                            builder.assign_stmt(
                                target="response",
                                value=response_model.build_load_expr(builder, builder.attr("raw_response")),
                            )
                            builder.yield_stmt(builder.attr("response"))
