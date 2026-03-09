from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack
from typing import Annotated, Any, get_args, get_origin

from app.statemachine.event import Event


class Depends:
    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


async def resolve_and_call(func: Callable[..., Any], event: Event | None) -> Any:
    sig = inspect.signature(func)
    hints = _get_type_hints_safe(func)
    kwargs: dict[str, Any] = {}

    async with AsyncExitStack() as stack:
        for param_name, param in sig.parameters.items():
            depends = _extract_depends(param_name, param, hints)
            if depends is not None:
                result = depends.dependency()
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, AsyncGenerator):
                    value = await stack.enter_async_context(_async_gen_context(result))
                else:
                    value = result
                kwargs[param_name] = value
            elif event is not None and _is_event_param(param_name, param, hints):
                kwargs[param_name] = event

        result = func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result


def _get_type_hints_safe(func: Callable[..., Any]) -> dict[str, Any]:
    try:
        return inspect.get_annotations(func, eval_str=True)
    except Exception:
        return {}


def _extract_depends(
    name: str, param: inspect.Parameter, hints: dict[str, Any]
) -> Depends | None:
    if isinstance(param.default, Depends):
        return param.default

    hint = hints.get(name)
    if hint is not None and get_origin(hint) is Annotated:
        for arg in get_args(hint)[1:]:
            if isinstance(arg, Depends):
                return arg

    return None


def _is_event_param(name: str, param: inspect.Parameter, hints: dict[str, Any]) -> bool:
    if name == "event":
        return True
    ann = hints.get(name, param.annotation)
    if ann is inspect.Parameter.empty:
        return False
    try:
        return isinstance(ann, type) and issubclass(ann, Event)
    except TypeError:
        return False


class _AsyncGenContextManager:
    def __init__(self, gen: AsyncGenerator[Any, None]) -> None:
        self._gen = gen

    async def __aenter__(self) -> Any:
        return await self._gen.__anext__()

    async def __aexit__(self, *exc_info: Any) -> None:
        try:
            await self._gen.__anext__()
        except StopAsyncIteration:
            pass


def _async_gen_context(gen: AsyncGenerator[Any, None]) -> _AsyncGenContextManager:
    return _AsyncGenContextManager(gen)
