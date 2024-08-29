"""
Base Models for defining steps
"""
from __future__ import annotations

import abc
import inspect
import typing

from functools import partial

import pydantic

from src.achain.utilities import callable_name
from src.achain.utilities import get_function_from_module_and_name

IT = typing.TypeVar("IT")
OT = typing.TypeVar("OT")

VariableParameters = typing.ParamSpec("VariableParameters")


class UnpickleablePydanticFieldMixin:
    @classmethod
    @abc.abstractmethod
    def _get_unpicklable_field_names(cls) -> typing.Collection[str]:
        ...

    @classmethod
    def _get_default_unpicklable_value(cls) -> typing.Union[typing.Dict[str, typing.Any], typing.Any]:
        return None

    def restore_fields(self):
        """
        Hook to add logic to run after __setstate__ is called
        """
        pass

    def __getstate__(self) -> typing.Union[dict[typing.Any, typing.Any], object]:
        state = super().__getstate__()
        if not isinstance(state, dict):
            return state

        default_unpicklable_value = self._get_default_unpicklable_value()

        for key in state.get("__dict__", {}):
            if key in self._get_unpicklable_field_names():
                if isinstance(default_unpicklable_value, dict):
                    state['__dict__'][key] = default_unpicklable_value.get(key, None)
                else:
                    state['__dict__'][key] = default_unpicklable_value

        for key in state.get("__pydantic_private__", {}):
            if key in self._get_unpicklable_field_names():
                if isinstance(default_unpicklable_value, dict):
                    state['__pydantic_private__'][key] = default_unpicklable_value.get(key, None)
                else:
                    state['__pydantic_private__'][key] = default_unpicklable_value

        return state

    def __setstate__(self, state: dict[typing.Any, typing.Any]) -> None:
        if hasattr(super(), "__setstate__"):
            getattr(super(), "__setstate__")(state)
        self.restore_fields()


class SerializableFunctionMixin(typing.Generic[IT, OT]):
    """
    A mixin that ensures that provides everything needed to serialize and call a function

    Classes that use this MUST define a `function` field that is a callable
    """
    module_name: str = pydantic.Field(
        default=None,
        description="The name of the module that contains the function to be called"
    )
    """The name of the module that contains the function to be called"""

    function_name: str = pydantic.Field(
        description="The name of the function to be called"
    )
    """The name of the function to be called"""

    args: typing.Optional[typing.Tuple[typing.Any, ...]] = pydantic.Field(
        default_factory=tuple,
        description="Positional arguments to pass to the function"
    )
    """Positional arguments to pass to the function"""

    kwargs: typing.Optional[typing.Dict[str, typing.Any]] = pydantic.Field(
        default_factory=dict,
        description="Keyword arguments to pass to the function"
    )
    """Keyword arguments to pass to the function"""

    @pydantic.model_validator(mode="before")
    @classmethod
    def ensure_has_function(cls, values: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        model_fields: typing.Optional[dict] = getattr(cls, "model_fields", None)

        if not isinstance(model_fields, typing.Mapping):
            raise pydantic.ValidationError(f"{cls.__name__} is meant to be used as a pydantic object but it is not")

        if "function" not in model_fields:
            raise pydantic.ValidationError(f"{cls.__name__} requires a `function` field and it is not present")

        return values

    @pydantic.model_validator(mode="before")
    @classmethod
    def assign_variables(
        cls,
        values: typing.Union[typing.Callable[[IT], OT], partial, typing.Dict[str, typing.Any]]
    ) -> typing.Dict[str, typing.Any]:
        """
        Make sure that a module_name and function_name are present if there's a function and vice versa

        :param values: Values that will be used to construct this object
        :return: The values that will be used to construct this object
        """
        if isinstance(values, partial):
            return {
                "module_name": inspect.getmodule(values.func).__name__,
                "function_name": values.func.__qualname__,
                "function": values,
            }

        if isinstance(values, SerializableFunctionMixin):
            return {
                "module_name": values.module_name,
                "function_name": values.function_name,
                "function": getattr(values, "function", None),
                "args": values.args,
                "kwargs": values.kwargs,
            }

        if isinstance(values, typing.Callable):
            function_name_parts = callable_name(values).split(".")
            module_name = '.'.join(function_name_parts[:-1])
            function_name = function_name_parts[-1]
            return {
                "module_name": module_name,
                "function_name": function_name,
                "function": values
            }

        if not isinstance(values, dict):
            raise pydantic.ValidationError(
                f"A function may only be dictated via a function, a partial function, or a mapping. "
                f"Received {values} (type={type(values)})"
            )

        if "module_name" in values and "function_name" in values and "function" in values:
            return values

        module_name = values.get("module_name")
        function_name = values.get("function_name")
        function = values.get("function")
        args = values.get("args")

        if isinstance(module_name, str) and isinstance(function_name, str) and not isinstance(
                function,
                typing.Callable
        ):
            values['function'] = get_function_from_module_and_name(module_name, function_name)

        if not (isinstance(module_name, str) and isinstance(function_name, str)) and isinstance(function, str):
            split_function_name = function.split(".")
            module_name = '.'.join(split_function_name[:-1])
            function_name = split_function_name[-1]

            values.update(
                module_name=module_name,
                function_name=function_name,
                function=get_function_from_module_and_name(module_name, function_name)
            )

        if not (isinstance(module_name, str) and isinstance(function_name, str)) and isinstance(
                function,
                typing.Callable
        ):
            values.update(
                module_name=function.__module__,
                function_name=function.__qualname__,
            )

        if args and (not isinstance(args, typing.Iterable) or isinstance(args, (str, bytes))):
            args = tuple([args])
            values['args'] = args

        if args and not isinstance(args, tuple):
            values['args'] = tuple(args)

        return values


class Step(abc.ABC, pydantic.BaseModel, typing.Generic[IT, OT]):
    """
    The base of a step to be performed
    """
    @abc.abstractmethod
    async def __call__(self, last_value: IT) -> OT:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @abc.abstractmethod
    def __str__(self):
        ...


class Function(SerializableFunctionMixin[IT, OT], Step[IT, OT], typing.Generic[IT, OT]):
    """
    The definition of a function to be performed

    Operates like a serializable `functools.partial`
    """
    function: typing.Optional[typing.Callable[[IT, VariableParameters], OT]] = pydantic.Field(
        default=None,
        description="The function to be called"
    )
    """The function to be called"""

    @property
    def name(self) -> str:
        return f"{self.module_name}.{self.function_name}"

    async def __call__(self, last_value: IT, *args, **kwargs) -> OT:
        args_to_call = [last_value]

        if self.args:
            args_to_call.extend(self.args)

        if args:
            args_to_call.extend(*args)

        if kwargs:
            kwargs = {**self.kwargs, **kwargs}
        else:
            kwargs = self.kwargs

        if kwargs:
            result = self.function(*args_to_call, **kwargs)
        else:
            result = self.function(*args_to_call)

        while inspect.isawaitable(result):
            result = await result

        return result

    def full_description(self, input_value: IT) -> str:
        description = f"{self.module_name}.{self.function_name}("

        description += f'"{input_value}"' if isinstance(input_value, str) else str(input_value)

        if self.args:
            args = [
                f'"{arg}"' if isinstance(arg, str) else str(arg)
                for arg in self.args
            ]
            description += f", {', '.join(str(arg) for arg in args)}"

        if self.kwargs:
            kwargs = []
            for key, value in self.kwargs.items():
                if isinstance(value, str):
                    value = f'"{value}"'
                kwargs.append(f'{key}={value}')
            description += f", {', '.join(kwargs)}"

        description += ")"
        return description

    def __str__(self):
        description = f"{self.module_name}.{self.function_name}(T"

        if self.args:
            args = [
                f'"{arg}"' if isinstance(arg, str) else str(arg)
                for arg in self.args
            ]
            description += f", {', '.join(str(arg) for arg in args)}"

        if self.kwargs:
            description += f", {', '.join(str(key) for key in self.kwargs)}"

        description += ")"
        return description


def call(function: typing.Callable[[IT, VariableParameters], OT], *args, **kwargs) -> Function[IT, OT]:
    return Function(
        function=function,
        args=args,
        kwargs=kwargs,
    )