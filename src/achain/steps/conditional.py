"""
Defines pydantic models that perform actions based on conditions
"""
from __future__ import annotations

import inspect
import typing

import pydantic

from .base import Step
from .base import Function

from src.achain.utilities import callable_name


IT = typing.TypeVar("IT")
"""An input type"""

TOT = typing.TypeVar("TOT")
"""The output type if a condition is true"""

FOT = typing.TypeVar("FOT")
"""The output type if a condition is false"""


class ConditionalStep(Step[IT, typing.Union[TOT, FOT]], typing.Generic[IT, TOT, FOT]):
    """
    Performs actions based on whether a predicate is true
    """
    predicate: Function = pydantic.Field(
        description="The predicate that decides what function to call"
    )
    """The predicate that decides what function to call"""

    true_function: typing.Optional[Function] = pydantic.Field(
        default=None,
        description="The function to call if the predicate is true. The input value is returned if there is no "
                    "handler for truth"
    )
    """The function to call if the predicate is true. The input value is returned if there is no handler for truth"""

    false_function: typing.Optional[Function] = pydantic.Field(
        default=None,
        description="The function to call if the predicate is false. The input value is returned if there is "
                    "no handler for false"
    )
    """The function to call if the predicate is false. The input value is returned if there is no handler for false"""

    async def __call__(self, last_value: IT) -> typing.Union[TOT, FOT]:
        if await self.predicate(last_value):
            result = self.true_function(last_value) if isinstance(self.true_function, typing.Callable) else last_value
        else:
            result = self.false_function(last_value) if isinstance(self.false_function, typing.Callable) else last_value

        while inspect.isawaitable(result):
            result = await result

        return result

    @pydantic.model_validator(mode="before")
    @classmethod
    def has_true_or_false(cls, values: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        """
        Ensure that either the true_function or false_function are available

        :param values: The values used to create this object
        :return: The values used to create this object
        """
        if not values.get("true_function") and not values.get("false_function"):
            raise pydantic.ValidationError(
                f"A true_function and/or false_function must be provided to create a {cls.__name__}, "
                f"but received neither."
            )

        return values

    @property
    def name(self) -> str:
        return callable_name(self.predicate)

    def __reduce__(self):
        constructor, mro, state = super().__reduce__()
        return constructor, mro, state

    def __str__(self):
        predicate = f"{callable_name(self._predicate)}(T)"

        true_name = str(self.true_function) if self.true_function else ""
        false_name = str(self.false_function) if self.false_function else ""

        if true_name and false_name:
            return f"if {predicate} then {true_name} else {false_name}"
        if not true_name:
            return f"{false_name} if not {predicate}"
        return f"{true_name} if {predicate}"
