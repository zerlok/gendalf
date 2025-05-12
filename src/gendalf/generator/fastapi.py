import typing as t

from astlab import package
from astlab.abc import Expr, TypeRef
from astlab.builder import (
    AttrASTBuilder,
    ClassBodyASTBuilder,
    ClassRefBuilder,
    FuncBodyASTBuilder,
    ModuleASTBuilder,
    PackageASTBuilder,
    ScopeASTBuilder,
)
from astlab.info import ModuleInfo, TypeInfo

from gendalf._typing import assert_never, override
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult
from gendalf.generator.transport_model.builder import TMBuilder
from gendalf.generator.transport_model.factory import PydanticTMFactory
from gendalf.model import (
    EntrypointInfo,
    MethodInfo,
    ParameterInfo,
    StreamStreamMethodInfo,
    UnaryUnaryMethodInfo,
)
from gendalf.string_case import camel2snake, snake2camel


class FastAPITypeRegistry:
    def __init__(self, context: CodeGeneratorContext, builder: ModuleASTBuilder) -> None:
        self.__builder = TMBuilder(builder, PydanticTMFactory())
        self.__builder.update(set(self.__iter_types(context)))

        self.__requests = dict[tuple[str, str], ClassRefBuilder]()
        self.__responses = dict[tuple[str, str], ClassRefBuilder]()

    def get_request(self, entrypoint: EntrypointInfo, method: MethodInfo) -> ClassRefBuilder:
        return self.__requests[(entrypoint.name, method.name)]

    def get_response(self, entrypoint: EntrypointInfo, method: MethodInfo) -> t.Optional[ClassRefBuilder]:
        return self.__responses.get((entrypoint.name, method.name))

    def request_param_unpack_expr(
        self,
        source: AttrASTBuilder,
        param: ParameterInfo,
        builder: FuncBodyASTBuilder,
    ) -> Expr:
        return self.__builder.assign_expr(source.attr(param.name), param.type_, "original", builder)

    def response_payload_pack_expr(
        self,
        source: AttrASTBuilder,
        annotation: TypeInfo,
        builder: FuncBodyASTBuilder,
    ) -> Expr:
        return self.__builder.assign_expr(source, annotation, "model", builder)

    def register_request(
        self,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
        fields: t.Mapping[str, TypeInfo],
        doc: t.Optional[str],
    ) -> None:
        model_ref = self.__builder.create_def(self.__create_model_name(entrypoint, method, "Request"), fields, doc)
        self.__requests[(entrypoint.name, method.name)] = model_ref

    def register_response(
        self,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
        fields: t.Mapping[str, TypeInfo],
        doc: t.Optional[str],
    ) -> None:
        model_ref = self.__builder.create_def(self.__create_model_name(entrypoint, method, "Response"), fields, doc)
        self.__responses[(entrypoint.name, method.name)] = model_ref

    def __create_model_name(
        self,
        entrypoint: EntrypointInfo,
        method: MethodInfo,
        suffix: str,
    ) -> str:
        return "".join(snake2camel(s) for s in (entrypoint.name, method.name, suffix))

    @staticmethod
    def __iter_types(context: CodeGeneratorContext) -> t.Iterable[TypeInfo]:
        for entrypoint in context.entrypoints:
            for method in entrypoint.methods:
                if isinstance(method, UnaryUnaryMethodInfo):
                    for param in method.params:
                        yield param.type_

                    if method.returns is not None:
                        yield method.returns

                elif isinstance(method, StreamStreamMethodInfo):
                    yield method.input_.type_
                    if method.output is not None:
                        yield method.output

                else:
                    assert_never(method)


class FastAPICodeGenerator(CodeGenerator):
    @override
    def generate(self, context: CodeGeneratorContext) -> CodeGeneratorResult:
        with package(context.package or "api") as pkg:
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
    ) -> FastAPITypeRegistry:
        with pkg.module("model") as mod:
            registry = FastAPITypeRegistry(context, mod)

            for entrypoint in context.entrypoints:
                for method in entrypoint.methods:
                    if isinstance(method, UnaryUnaryMethodInfo):
                        registry.register_request(
                            entrypoint=entrypoint,
                            method=method,
                            fields={param.name: param.type_ for param in method.params},
                            doc=f"Request model for `{entrypoint.name}.{method.name}` entrypoint method",
                        )

                        if method.returns is not None:
                            registry.register_response(
                                entrypoint=entrypoint,
                                method=method,
                                fields={"payload": method.returns},
                                doc=f"Response model for `{entrypoint.name}.{method.name}` entrypoint method",
                            )

                    elif isinstance(method, StreamStreamMethodInfo):
                        registry.register_request(
                            entrypoint=entrypoint,
                            method=method,
                            fields={method.input_.name: method.input_.type_},
                            doc=f"Request model for `{entrypoint.name}.{method.name}` entrypoint method",
                        )

                        if method.output is not None:
                            registry.register_response(
                                entrypoint=entrypoint,
                                method=method,
                                fields={"payload": method.output},
                                doc=f"Response model for `{entrypoint.name}.{method.name}` entrypoint method",
                            )

                    else:
                        assert_never(method)

        return registry

    def __build_server_module(
        self,
        context: CodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: FastAPITypeRegistry,
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
        registry: FastAPITypeRegistry,
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
        registry: FastAPITypeRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        request_ref = registry.get_request(entrypoint, method)
        response_ref = registry.get_response(entrypoint, method)

        with (
            builder.method_def(method.name)
            .arg("request", request_ref)
            .returns(response_ref or builder.none())
            .async_() as method_def
        ):
            for param in method.params:
                builder.assign_stmt(
                    target=f"input_{param.name}",
                    value=registry.request_param_unpack_expr(builder.attr("request"), param, method_def),
                )

            impl_call = method_def.self_attr("impl", method.name).call(
                kwargs={param.name: builder.attr(f"input_{param.name}") for param in method.params}
            )

            if method.returns is not None and response_ref is not None:
                builder.assign_stmt("output", impl_call)
                builder.assign_stmt(
                    "response",
                    builder.call(response_ref).kwarg(
                        "payload",
                        registry.response_payload_pack_expr(builder.attr("output"), method.returns, method_def),
                    ),
                )
                builder.return_stmt(builder.attr("response"))

            else:
                builder.stmt(impl_call)

    def __build_server_handler_method_stream_stream(
        self,
        builder: ClassBodyASTBuilder,
        registry: FastAPITypeRegistry,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        request_ref = registry.get_request(entrypoint, method)
        response_ref = registry.get_response(entrypoint, method)

        if method.output is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        if response_ref is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        with (
            builder.method_def(method.name)
            .arg("websocket", TypeInfo("WebSocket", ModuleInfo(None, "fastapi")))
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
                        value=self.__build_model_load_expr(builder, request_ref, "request_text"),
                    )
                    builder.yield_stmt(
                        registry.request_param_unpack_expr(builder.attr("request"), method.input_, method_def)
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
                            value=builder.call(response_ref).kwarg(
                                "payload",
                                registry.response_payload_pack_expr(builder.attr("output"), method.output, method_def),
                            ),
                        )
                        builder.stmt(
                            builder.attr("websocket", "send_text")
                            .call()
                            .arg(self.__build_model_dump_expr(builder, "response"))
                            .await_()
                        )

                with try_stmt.except_(TypeInfo("WebSocketDisconnect", ModuleInfo(None, "fastapi"))):
                    pass

    def __build_server_entrypoint_router(
        self,
        builder: ModuleASTBuilder,
        entrypoint: EntrypointInfo,
        handler_def: TypeRef,
    ) -> None:
        fastapi_router_ref = TypeInfo("APIRouter", ModuleInfo(None, "fastapi"))

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
        registry: FastAPITypeRegistry,
    ) -> None:
        client_impl_ref = TypeInfo("AsyncClient", ModuleInfo(None, "httpx"))

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
        registry: FastAPITypeRegistry,
        entrypoint: EntrypointInfo,
        method: UnaryUnaryMethodInfo,
    ) -> None:
        response_def = registry.get_response(entrypoint, method)
        with (
            builder.method_def(method.name)
            .arg("request", registry.get_request(entrypoint, method))
            .returns(response_def or builder.const(None))
            .async_() as method_def
        ):
            request_call_expr = (
                method_def.self_attr("impl", "post")
                .call()
                .kwarg("url", builder.const(f"/{camel2snake(entrypoint.name)}/{method.name}"))
                .kwarg("json", self.__build_model_dump_expr(builder, "request", intermediate=True))
                .await_()
            )

            if method.returns is not None and response_def is not None:
                builder.assign_stmt("raw_response", request_call_expr)
                builder.assign_stmt(
                    target="response",
                    value=self.__build_model_load_expr(
                        builder, response_def, builder.attr("raw_response", "read").call()
                    ),
                )
                builder.return_stmt(builder.attr("response"))

            else:
                builder.stmt(request_call_expr)

    def __build_client_method_stream_stream(
        self,
        builder: ClassBodyASTBuilder,
        registry: FastAPITypeRegistry,
        entrypoint: EntrypointInfo,
        method: StreamStreamMethodInfo,
    ) -> None:
        ws_connect_ref = TypeInfo("aconnect_ws", ModuleInfo(None, "httpx_ws"))
        ws_session_ref = TypeInfo("AsyncWebSocketSession", ModuleInfo(None, "httpx_ws"))
        ws_error_refs = [
            TypeInfo("WebSocketNetworkError", ModuleInfo(None, "httpx_ws")),
            TypeInfo("WebSocketDisconnect", ModuleInfo(None, "httpx_ws")),
        ]
        task_group_ref = TypeInfo("TaskGroup", ModuleInfo(None, "asyncio"))

        request_ref = registry.get_request(entrypoint, method)
        response_ref = registry.get_response(entrypoint, method)

        if method.output is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        if response_ref is None:
            detail = "invalid method"
            raise ValueError(detail, method)

        with (
            builder.method_def(method.name)
            .arg("requests", request_ref.iterator(is_async=True))
            .returns(response_ref.iterator(is_async=True))
            .async_() as method_def
        ):
            with builder.func_def("send_requests").arg("ws", ws_session_ref).returns(builder.none()).async_():
                with builder.try_stmt() as try_stmt:
                    with try_stmt.body():
                        with builder.for_stmt("request", builder.attr("requests")).async_():
                            builder.stmt(
                                builder.attr("ws", "send_text")
                                .call()
                                .arg(self.__build_model_dump_expr(builder, "request"))
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

                with builder.while_stmt(builder.not_(builder.attr("sender", "done").call())):
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
                                value=self.__build_model_load_expr(builder, response_ref, "raw_response"),
                            )
                            builder.yield_stmt(builder.attr("response"))

    def __build_model_load_expr(self, builder: ScopeASTBuilder, model: TypeRef, source: t.Union[str, Expr]) -> Expr:
        return (
            builder.attr(model, "model_validate_json")
            .call()
            .arg(builder.attr(source) if isinstance(source, str) else source)
        )

    def __build_model_dump_expr(
        self,
        builder: ScopeASTBuilder,
        source: str,
        *,
        intermediate: bool = False,
    ) -> Expr:
        return (
            builder.attr(source, "model_dump_json" if not intermediate else "model_dump")
            .call(kwargs={"mode": builder.const("json")} if intermediate else None)
            .kwarg("by_alias", builder.const(value=True))
            .kwarg("exclude_none", builder.const(value=True))
        )
