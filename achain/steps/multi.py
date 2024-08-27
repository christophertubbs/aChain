"""
Defines Pydantic Models that handle multiple things at once
"""
from __future__ import annotations

import concurrent.futures as futures
import typing
import asyncio
import inspect

from weakref import ref as reference

import pydantic

from .base import Step
from .base import Function
from .base import UnpickleablePydanticFieldMixin
from ..utilities import callable_name

T = typing.TypeVar("T")


class MultipleActionStep(UnpickleablePydanticFieldMixin, Step[T, T], typing.Generic[T]):
    """
    Performs several actions at once

    The output of this step will be identical to the input
    """
    functions: typing.List[Function] = pydantic.Field(
        description="List of functions to perform",
    )
    """The functions to perform all at once"""

    @classmethod
    def _get_unpicklable_field_names(cls) -> typing.Collection[str]:
        return ["_thread_pool"]

    _thread_pool: reference[futures.ThreadPoolExecutor] = pydantic.PrivateAttr(default=None)

    def set_thread_pool(self, pool: futures.ThreadPoolExecutor) -> typing.Self:
        self._thread_pool = reference(pool)
        return self

    def add_step(self, step: typing.Union[Step[T, typing.Any], typing.Callable[[T], typing.Any]], *args, **kwargs) -> typing.Self:
        """
        Add a step to be performed

        Args:
            step: The action to be performed

        Returns:
            This MultipleActionStep instance
        """
        if inspect.isroutine(step):
            step = Function(function=step)
        self._steps.append(step)
        return self

    async def __call__(self, last_value: T) -> T:
        thread_pool = None
        created_thread_pool = False

        try:
            if self._thread_pool is None:
                thread_pool = futures.ThreadPoolExecutor()
                created_thread_pool = True
            else:
                thread_pool = self._thread_pool()

            actions: typing.List[futures.Future] = [
                thread_pool.submit(step, last_value)
                for step in self.functions
            ]
            while actions:
                action = actions.pop()
                try:
                    result = action.result(timeout=0.05)
                    while inspect.isawaitable(result):
                        result = await result
                except futures.TimeoutError:
                    actions.append(action)
        except BaseException as exc:
            raise
        finally:
            if created_thread_pool:
                thread_pool.shutdown()
                del thread_pool

        return last_value


    @property
    def name(self) -> str:
        return f"{self.__class__.__name__}({', '.join(callable_name(function) for function in self.functions)}"

    def __str__(self):
        return f"In Parallel: [{', '.join(function.name for function in self.functions)}]"
