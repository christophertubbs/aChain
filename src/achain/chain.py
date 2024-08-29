"""
Defines the core chain object
"""
from __future__ import annotations

import inspect
import logging
from functools import partial
import asyncio

from concurrent.futures import ThreadPoolExecutor

import pydantic
import typing_extensions as typing

from src.achain.exceptions import StepError
from src.achain.steps import ExceptionStep
from src.achain.steps import Function
from src.achain.steps import ConditionalStep
from src.achain.steps import MultipleActionStep
from src.achain.steps.base import Step
from src.achain.steps.base import UnpickleablePydanticFieldMixin

LOGGER = logging.getLogger(__name__)

IT = typing.TypeVar("IT")
"""Represents the type that will be the input of a step"""

TT = typing.TypeVar("TT")
"""The type returned when a conditional step is true"""

FT = typing.TypeVar("FT")
"""The type returned when a conditional step is false"""

ET = typing.TypeVar("ET", bound=BaseException, covariant=True)
"""A type of error"""

RT = typing.TypeVar("RT")
"""Represents the type that a chain will return"""

OT = typing.TypeVar("OT")
"""Some type of new output type"""

VariableParameters = typing.ParamSpec("VariableParameters")


def step_from_dict(specification: typing.MutableMapping[str, typing.Any]) -> Step[IT, OT]:
    step_types: typing.List[typing.Union[typing.Type[Step[IT, OT]], typing.Type[ExceptionStep[IT, ET, OT]]]] = [
        ExceptionStep,
        ConditionalStep,
        MultipleActionStep,
        Function
    ]

    for step_type in step_types:
        try:
            step = step_type.model_validate(specification)
            return step
        except:
            pass

    raise Exception(f"Cannot create a step from a dictionary - it does not have the required types and values")


class _BasicProducer(typing.Callable, typing.Generic[RT]):
    """
    A simple callable that will just return the value given to it. Used for when a callable isn't passed as a
    starting function in a chain
    """
    def __init__(self, value: RT = None):
        self.__value = value

    def __call__(self, *args, **kwargs) -> RT:
        if args:
            return args

        if kwargs:
            return kwargs

        return self.__value


class Chain(UnpickleablePydanticFieldMixin, pydantic.BaseModel, typing.Generic[RT]):
    """
    Creates a chain of functions that transform data in a specified order
    """

    @classmethod
    def _get_unpicklable_field_names(cls) -> typing.Collection[str]:
        return ["_thread_pool"]

    def restore_fields(self):
        for step in [step for step in self.stack if isinstance(step, MultipleActionStep)]:
            if self._thread_pool is None:
                self._thread_pool = ThreadPoolExecutor()
            step.set_thread_pool(self._thread_pool)

    beginning: typing.Callable[[VariableParameters], RT] = pydantic.Field(
        description="The producer of the first value in the chain"
    )
    stack: typing.List[typing.Union[Step, ExceptionStep]] = pydantic.Field(default_factory=list)
    args: typing.Sequence[typing.Any] = pydantic.Field(default_factory=list)
    kwargs: typing.Mapping[str, typing.Any] = pydantic.Field(default_factory=dict)
    _logger: logging.Logger = pydantic.PrivateAttr(default=LOGGER)
    _thread_pool: ThreadPoolExecutor = pydantic.PrivateAttr(default=None)

    def __init__(
        self,
        beginning: typing.Callable[[VariableParameters], RT],
        args: typing.Sequence[typing.Any] = None,
        kwargs: typing.Mapping[str, typing.Any] = None,
        **fields
    ):
        if not callable(beginning):
            beginning = _BasicProducer(beginning)
        super().__init__(beginning=beginning, args=args or [], kwargs=kwargs or {}, **fields)

        for step in [step for step in self.stack if isinstance(step, MultipleActionStep)]:
            if self._thread_pool is None:
                self._thread_pool = ThreadPoolExecutor()
            step.set_thread_pool(self._thread_pool)

    @pydantic.field_validator('beginning', mode='before')
    @classmethod
    def set_producer(cls, value: typing.Any) -> typing.Any:
        """
        Set a producer function if one is not passed or the one passed isn't callable

        :param value: The passed value
        :return: The passed value in a callable state
        """
        if isinstance(value, typing.Callable):
            return value

        return _BasicProducer(value)

    def when(
        self,
        __predicate: typing.Union[typing.Callable[[RT, VariableParameters], bool], partial[bool]],
        /,
        then: typing.Union[typing.Callable[[RT, VariableParameters], TT], partial[TT]] = None,
        otherwise: typing.Union[typing.Callable[[RT, VariableParameters], FT], partial[TT]] = None,
        *,
        then_args: typing.Sequence[typing.Any] = None,
        then_kwargs: typing.Dict[str, typing.Any] = None,
        otherwise_args: typing.Sequence[typing.Any] = None,
        otherwise_kwargs: typing.Dict[str, typing.Any] = None,
    ) -> Chain[typing.Union[TT, FT]]:
        if self._thread_pool is None:
            self._thread_pool = ThreadPoolExecutor()

        step: Step[RT, typing.Union[TT, FT]] = ConditionalStep(
            predicate=__predicate,
            true_function=then,
            true_args=then_args,
            true_kwargs=then_kwargs,
            false_function=otherwise,
            false_args=otherwise_args,
            false_kwargs=otherwise_kwargs,
        )
        self.stack.append(step)
        return self

    def then(
        self,
        function: typing.Union[
            typing.Callable[[RT, VariableParameters], OT],
            typing.Callable[[RT], OT],
            partial[OT],
            typing.MutableMapping[str, typing.Any]
        ],
        *args,
        **kwargs
    ) -> Chain[OT]:
        if isinstance(function, typing.MutableMapping):
            step: [RT, OT] = step_from_dict(function)
        else:
            step: Step[RT, OT] = Function(function=function, args=args, kwargs=kwargs)
        self.stack.append(step)
        return self

    def all(
        self,
        *functions: typing.Union[
            typing.Callable[[RT, VariableParameters], typing.Any],
            typing.Callable[[RT], typing.Any],
            typing.Dict[str, typing.Any],
            partial
        ]
    ) -> Chain[RT]:
        if self._thread_pool is None:
            self._thread_pool = ThreadPoolExecutor()

        functions = [
            step_from_dict(function) if isinstance(function, typing.Dict) else function
            for function in functions
        ]

        step = MultipleActionStep(
            functions=functions,
        )
        step.set_thread_pool(self._thread_pool)
        self.stack.append(step)

        return self

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = LOGGER
        return self._logger

    @logger.setter
    def debug(self, value: logging.Logger) -> None:
        self._logger = value

    def exception(
        self,
        handler: typing.Union[typing.Callable[[RT, ET], OT], typing.Dict[str, typing.Any]],
        *,
        return_on_fail: bool = False
    ) -> Chain[OT]:
        if isinstance(handler, typing.Dict):
            step = ExceptionStep(**handler)
        else:
            step = ExceptionStep(function=handler, return_on_fail=return_on_fail)
        self.stack.append(step)
        return self

    def __await__(self):
        return self.execute().__await__()

    async def __call__(self, *args, **kwargs) -> RT:
        return await self.execute(*args, **kwargs)

    async def execute(self, *args, **kwargs) -> RT:
        last_exception: typing.Optional[BaseException] = None
        current_value: typing.Any = None

        try:
            args = [*self.args, *args]
            kwargs = {**self.kwargs, **kwargs}
            current_value = self.beginning(*args, **kwargs)

            while inspect.isawaitable(current_value):
                current_value = await current_value
        except BaseException as exception:
            last_exception = exception

        for step_index, step in enumerate(self.stack):
            if isinstance(step, ExceptionStep) and not isinstance(last_exception, BaseException):
                continue
            if isinstance(last_exception, BaseException) and not isinstance(step, ExceptionStep):
                if step_index == 0 or isinstance(last_exception, StepError):
                    raise last_exception

                message = (
                    f"Could not execute step ({step_index}/{len(self.stack)}): "
                    f"{self.stack[step_index - 1]}: {type(last_exception).__qualname__} {last_exception}."
                )

                if last_exception.__doc__:
                    message = f"{message} {last_exception.__doc__}"

                step_error = StepError(message)
                step_error.__traceback__ = last_exception.__traceback__
                raise step_error

            if isinstance(last_exception, BaseException) and isinstance(step, ExceptionStep):
                try:
                    current_value = await step(current_value, last_exception)
                    last_exception = None
                    if step.return_on_fail:
                        return current_value
                except BaseException as exception:
                    last_exception = exception
            else:
                try:
                    current_value = await step(current_value)
                except BaseException as exception:
                    last_exception = exception

            while inspect.isawaitable(current_value):
                try:
                    current_value = await current_value
                except BaseException as exception:
                    last_exception = exception

            if self.debug:
                LOGGER.info(f"Completed {step_index}) {step}")

        if last_exception:
            raise last_exception

        return current_value

    def execute_synchronously(self, *args, **kwargs) -> RT:
        return asyncio.run(self.execute(*args, **kwargs))

    def __del__(self):
        if self._thread_pool is not None:
            self._thread_pool.shutdown()
