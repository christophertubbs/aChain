"""
Defines Pydantic Models to perform simple actions
"""
from __future__ import annotations

import importlib
from typing import Union, Callable

import inspect
import pydantic

import typing_extensions as typing

from .base import OT
from .base import Step

IT = typing.TypeVar('IT')
RT = typing.TypeVar("RT")
VariableParameters = typing.ParamSpec("VariableParameters")


class ActionStep(Step[IT, RT]):
    """
    Performs a singular action
    """
    module: typing.Optional[str] = pydantic.Field(
        default=None,
        description="The name of the module that contains the function to call"
    )
    """The name of the module that contains the function to call"""

    function_name: typing.Optional[str] = pydantic.Field(default=None, description="The name of the function to call")
    """The name of the function to call"""

    handler: typing.Optional[Union[Callable[[IT], RT], Callable[[IT, VariableParameters], RT]]] = pydantic.Field(
        default=None,
        description="The function to call"
    )
    """The function to call"""

    args: typing.Optional[typing.List[typing.Any]] = pydantic.Field(
        default_factory=list,
        description="Positional arguments to use when calling the function"
    )
    """Positional arguments to use when calling the function"""

    kwargs: typing.Optional[typing.Dict[str, typing.Any]] = pydantic.Field(
        default_factory=dict,
        description="Keyword arguments to use when calling the function"
    )
    """Keyword arguments to use when calling the function"""

    @pydantic.model_validator(mode="before")
    @classmethod
    def assign_handler(cls, value: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        module_name = value['module'] if isinstance(value.get("module"), str) else None
        function_name = value['function_name'] if isinstance(value.get("function_name"), str) else None
        handler = value['handler'] if isinstance(value.get("handler"), (str, typing.Callable)) else None

        if not (module_name and function_name or handler):
            raise pydantic.ValidationError(
                f"A module and function name or callable function are required to create an {cls.__name__}, "
                f"but none were provided"
            )

        if isinstance(handler, str) and not (module_name and function_name):
            handler_parts = handler.split(".")
            module_name = '.'.join(handler_parts[:-1])
            function_name = handler_parts[-1]
            value['module'] = module_name
            value['function_name'] = function_name

        if module_name and function_name and not isinstance(handler, typing.Callable):
            given_module = importlib.import_module(value["module"])
            intended_function = getattr(given_module, value["function_name"], None)

            if not intended_function:
                raise ValueError(
                    f"There is not function to be called named {value['function_name']} in module {value['module_name']}"
                )

            if not isinstance(intended_function, typing.Callable):
                raise ValueError(
                    f"{value['module']}.{value['function_name']} is not callable"
                )

            value['handler'] = intended_function

        if isinstance(handler, typing.Callable) and not (module_name and function_name):
            value['module'] = handler.__module__
            value['function_name'] = handler.__qualname__

        return value

    async def __call__(self, last_value: IT) -> OT:
        if self.args and self.kwargs:
            result = self.handler(last_value, *self.args, **self.kwargs)
        elif self.args:
            result = self.handler(last_value, *self.args)
        elif self.kwargs:
            result = self.handler(last_value, **self.kwargs)
        else:
            result = self.handler(last_value)

        while inspect.isawaitable(result):
            original_result = result
            result = await result

            if result == original_result:
                break

        return result

    @property
    def name(self) -> str:
        return f"{self.module}.{self.function_name}"

    def __str__(self):
        return (
            f"{self.name}"
            f"(T{', ' + ', '.join(str(arg) for arg in self.args)}"
            f"{', ' + ', '.join(str(key) for key in self.kwargs.keys())})"
        )
