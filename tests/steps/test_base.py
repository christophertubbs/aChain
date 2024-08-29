"""
Tests for achain.steps.base
"""
import inspect
import typing
import asyncio
import pickle

from unittest import IsolatedAsyncioTestCase

from src.achain.steps import Function

SLEEP_SECONDS = 0.03
INPUT_VALUE: int = 10

async def async_function(value: int, *args, **kwargs) -> bool:
    if not args:
        args = (1,)

    args = tuple([
        arg.real if isinstance(arg, complex) else arg
        for arg in args
        if isinstance(arg, (int, float, complex))
    ])

    await asyncio.sleep(SLEEP_SECONDS)

    kwarg_values = tuple([
        value.real if isinstance(value, complex) else value
        for value in kwargs.values()
        if isinstance(value, (int, float, complex))
    ])

    await asyncio.sleep(SLEEP_SECONDS)

    total_of_args = sum(args) or 1
    sum_of_kwarg_values = sum(kwarg_values) or 1

    return (value * sum_of_kwarg_values) / total_of_args % 2 == 0


def sync_function(value: int, *args, **kwargs) -> bool:
    if not args:
        args = (1,)

    args = tuple([
        arg.real if isinstance(arg, complex) else arg
        for arg in args
        if isinstance(arg, (int, float, complex))
    ])

    kwarg_values = tuple([
        value.real if isinstance(value, complex) else value
        for value in kwargs.values()
        if isinstance(value, (int, float, complex))
    ])

    total_of_args = sum(args) or 1
    sum_of_kwarg_values = sum(kwarg_values) or 1

    return (value * sum_of_kwarg_values) / total_of_args % 3 == 0


def make_functions_and_expectations() -> typing.List[typing.Tuple[Function, bool]]:
    functions_and_expectations: typing.List[typing.Tuple[Function, bool]] = []

    # Add the `async_function` expectations'
    first = Function(function=async_function, args=(4,), kwargs={})  # 2.5 % 2 == 0
    functions_and_expectations.append((first, False))

    second = Function(function=async_function, args=(0.2,), kwargs={})  # 50.0 % 2 == 0
    functions_and_expectations.append((second, True))

    third = Function(function=async_function, args=(), kwargs={"one": 10})  # 100.0 % 2 == 0
    functions_and_expectations.append((third, True))

    fourth = Function(function=async_function, args=(0.2,), kwargs={"one": 10})  # 500.0 % 2 == 0
    functions_and_expectations.append((fourth, True))

    fifth = Function(function=async_function, args=(0.2, 2.8), kwargs={"one": 10})  # 33.33333 % 2 == 0
    functions_and_expectations.append((fifth, False))

    sixth = Function(function=async_function, args=(0.2, 2.8), kwargs={"one": 10, "two": 14})  # 80.0 % 2 == 0
    functions_and_expectations.append((sixth, True))

    # Add `async_function` expectations with function definitions that aren't functions
    first = Function(function="tests.steps.test_base.async_function", args=(4,), kwargs={})  # 2.5 % 2 == 0
    functions_and_expectations.append((first, False))

    second = Function(
        module_name="tests.steps.test_base",
        function_name="async_function",
        args=(0.2,),
        kwargs={}
    )  # 50.0 % 2 == 0
    functions_and_expectations.append((second, True))

    # Add the `sync_function` expectations
    first = Function(function=sync_function, args=(4,), kwargs={})  # 2.5 % 3 == 0
    functions_and_expectations.append((first, False))

    second = Function(function=sync_function, args=(3.3333333333333333333,), kwargs={})  # 3.0 % 3 == 0
    functions_and_expectations.append((second, True))

    third = Function(function=sync_function, args=(), kwargs={"one": 3})  # 30.0 % 3 == 0
    functions_and_expectations.append((third, True))

    fourth = Function(function=sync_function, args=(3.3333333333333333333,), kwargs={"one": 3})  # 9.0 % 3 == 0
    functions_and_expectations.append((fourth, True))

    fifth = Function(function=sync_function, args=(0.2, 2.8), kwargs={"one": 3})  # 10.0 % 3 == 0
    functions_and_expectations.append((fifth, False))

    sixth = Function(
        function=sync_function,
        args=(3.3333333333333333333, 6.66666666666666666),
        kwargs={"one": 3, "two": 6}
    )  # 9.0 % 3 == 0
    functions_and_expectations.append((sixth, True))

    return functions_and_expectations


class TestBase(IsolatedAsyncioTestCase):
    async def test_function_call(self):
        functions = make_functions_and_expectations()

        for function, expectation in functions:
            result = function(INPUT_VALUE)

            while inspect.isawaitable(result):
                result = await result

            self.assertEqual(
                result,
                expectation,
                f"{function.full_description(INPUT_VALUE)} should return {expectation} but returned {result}"
            )

    async def test_pickling(self):
        functions = make_functions_and_expectations()

        for function, expectation in functions:
            pickled_function = pickle.loads(pickle.dumps(function))
            normal_result = function(INPUT_VALUE)

            while inspect.isawaitable(normal_result):
                normal_result = await normal_result

            pickled_result = pickled_function(INPUT_VALUE)

            while inspect.isawaitable(pickled_result):
                pickled_result = await pickled_result

            self.assertEqual(normal_result, pickled_result)
