"""
Defines Pydantic Models that handle exceptions
"""
from __future__ import annotations

import inspect

import typing_extensions as typing

import pydantic

from .base import SerializableFunctionMixin

from src.achain.utilities import callable_name
from src.achain.utilities import function_and_args_to_str

IT = typing.TypeVar("IT")
"""Indicates an input type"""

OT = typing.TypeVar("OT")
"""Indicates an output type"""

ET = typing.TypeVar("ET", bound=BaseException, covariant=True)
"""Indicates an exception type"""

VariableParameters = typing.ParamSpec("VariableParameters")
"""Represents an optional *args and **kwargs for a function signature"""


class ExceptionStep(pydantic.BaseModel, SerializableFunctionMixin[IT, OT], typing.Generic[IT, OT, ET]):
    """
    Performs specialized handling for an exception
    """
    function: typing.Union[typing.Callable[[IT, ET, VariableParameters], OT], typing.Callable[[IT, ET], OT]] = pydantic.Field(
        description="The function to be called"
    )
    """The function to be called"""

    return_on_fail: bool = pydantic.Field(
        description="Whether to exit the processing chain with the produced value"
    )
    """Whether to exit the processing chain with the produced value"""

    async def __call__(self, last_value: IT, error: ET) -> OT:
        if self.args and self.kwargs:
            result = self.function(last_value, error, *self.args, **self.kwargs)
        elif self.args:
            result = self.function(last_value, error, *self.args)
        elif self.kwargs:
            result = self.function(last_value, error, **self.kwargs)
        else:
            result = self.function(last_value, error)

        while inspect.isawaitable(result):
            original_result = result

            result = await result

            if result == original_result:
                break

        return result

    @property
    def name(self) -> str:
        return callable_name(self.handler)

    def __str__(self):
        return (
            f"{function_and_args_to_str(self.function, self.args, self.kwargs, 'T', 'Exception')} "
            f"if previous step failed"
        )
