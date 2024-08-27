"""
Provides common functions that may be used throughout the library
"""
from __future__ import annotations

import importlib
import typing
import inspect


def callable_name(callable_object: typing.Any) -> str:
    """
    Determine the name of an object that may be called

    :param callable_object: The object that may be called
    :return: The name of the object to call
    """
    if inspect.isroutine(callable_object):
        return callable_object.__qualname__

    if hasattr(callable_object, "name"):
        return callable_object.name

    if hasattr(callable_object, "module_name") and hasattr(callable_object, "function_name"):
        return f"{callable_object.module_name}.{callable_object.function_name}"

    return callable_object.__class__.__qualname__


def function_and_args_to_str(function: typing.Callable, args: typing.Iterable, kwargs: typing.Mapping, *parameters) -> str:
    """
    Create a string representation of a function based on the function and values that will be passed to it

    :param function: The function to describe
    :param args: A collection of positional arguments
    :param kwargs: A collection of keyword arguments
    :param parameters: representation values for inputs that have not yet been defined
    :return: A string representation of a function
    """
    arguments = list(parameters)
    for arg in args:
        if isinstance(arg, typing.Callable):
            try:
                signature = str(inspect.signature(arg))
                signature = signature.replace("'", "")
                signature = signature.replace("->", "=>")

                function_description = f"{callable_name(arg)}{signature}"
            except:
                function_description = f"{callable_name(arg)}(...)"
            arguments.append(function_description)
        elif isinstance(arg, str):
            arguments.append(f'"{arg}"')
        else:
            arguments.append(str(arg))

    arguments.extend(kwargs.keys())

    return f"{callable_name(function)}({', '.join(arguments)})"


def get_function_from_module_and_name(module_name: str, function_name: str) -> typing.Callable:
    """
    Get a function from a module name and a function name

    :param module_name: The name of the module that contains the function
    :param function_name: The name of the function that will be called
    :return: A function from a module name and a function name
    """
    module = importlib.import_module(module_name)

    if not hasattr(module, function_name):
        raise KeyError(f"{module_name} has no function named {function_name}")

    function = getattr(module, function_name)

    if not inspect.isroutine(function):
        raise ValueError(f"{module_name}.{function_name} is not a function")

    return function


class DelayedFunction:
    """
    Prepares a function to be called later.

    Like a `functools.partial`, but the order of arguments is reliant on what is passed
    at the end rather than what is passed in the beginning.

    For example, the following two function calls are the same:

        from functools import partial

        def example(one: int, two: int, three: int, *args, **kwargs) -> int:
            return one + two
    """
    def __init__(self, function: typing.Callable, *args, **kwargs) -> None:
        self.__function = function
        self.__args = args
        self.__kwargs = kwargs
        self.__doc__ = function.__doc__

    @property
    def function(self) -> typing.Callable:
        return self.__function

    @property
    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.__function)

    @property
    def args(self) -> typing.Iterable:
        return self.__args

    @property
    def kwargs(self) -> typing.Mapping:
        return self.__kwargs

    def __call__(self, *args, **kwargs):
        args = [*args, *self.__args]
        kwargs = {**kwargs, **self.__kwargs}
        return self.__function(*args, **kwargs)