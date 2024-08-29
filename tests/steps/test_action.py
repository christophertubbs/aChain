from unittest import IsolatedAsyncioTestCase

import asyncio

from src.achain.steps import ActionStep


def sync_function(value: int, *args, **kwargs) -> int:
    return value * sum(args) + kwargs['one']


async def async_function(value: int, *args, **kwargs) -> int:
    await asyncio.sleep(0.2)
    return value * sum(args) + kwargs['one']


class TestActionStep(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.args = [9]
        self.kwargs = {"one": 2}
        self.sync_input = 3
        self.async_input = 4
        self.expected_sync_result = 29
        self.expected_async_result = 38

        self.specific_sync_step = ActionStep(handler=sync_function, args=self.args, kwargs=self.kwargs)
        self.sync_step_by_name = ActionStep(module="tests.steps.test_action", function_name="sync_function", args=self.args, kwargs=self.kwargs)
        self.sync_function_by_function_name = ActionStep(handler="tests.steps.test_action.sync_function", args=self.args, kwargs=self.kwargs)

        self.async_step = ActionStep(handler=async_function, args=self.args, kwargs={"one": 2})
        self.async_step_by_name = ActionStep(module="tests.steps.test_action", function_name="async_function", args=self.args, kwargs=self.kwargs)
        self.async_function_by_function_name = ActionStep(handler="tests.steps.test_action.async_function", args=self.args, kwargs=self.kwargs)

    def test_assign_handler(self):
        self.assertEqual(self.specific_sync_step.handler, sync_function)
        self.assertEqual(self.sync_step_by_name.handler, sync_function)
        self.assertEqual(self.sync_function_by_function_name.handler, sync_function)
        self.assertEqual(self.specific_sync_step.module, self.__module__)
        self.assertEqual(self.sync_step_by_name.module, self.__module__)
        self.assertEqual(self.sync_function_by_function_name.module, self.__module__)
        self.assertEqual(self.specific_sync_step.function_name, sync_function.__qualname__)
        self.assertEqual(self.sync_step_by_name.function_name, sync_function.__qualname__)
        self.assertEqual(self.sync_function_by_function_name.function_name, sync_function.__qualname__)

        self.assertEqual(self.async_step.handler, async_function)
        self.assertEqual(self.async_step_by_name.handler, async_function)
        self.assertEqual(self.async_function_by_function_name.handler, async_function)
        self.assertEqual(self.async_step.module, self.__module__)
        self.assertEqual(self.async_step_by_name.module, self.__module__)
        self.assertEqual(self.async_function_by_function_name.module, self.__module__)
        self.assertEqual(self.async_step.function_name, async_function.__qualname__)
        self.assertEqual(self.async_step_by_name.function_name, async_function.__qualname__)
        self.assertEqual(self.async_function_by_function_name.function_name, async_function.__qualname__)

    def test_name(self):
        sync_name = f"{self.__module__}.{sync_function.__qualname__}"
        async_name = f"{self.__module__}.{async_function.__qualname__}"

        self.assertEqual(sync_name, self.sync_step_by_name.name)
        self.assertEqual(sync_name, self.specific_sync_step.name)
        self.assertEqual(sync_name, self.sync_function_by_function_name.name)

        self.assertEqual(async_name, self.async_step.name)
        self.assertEqual(async_name, self.async_function_by_function_name.name)
        self.assertEqual(async_name, self.async_step_by_name.name)

    async def test_call(self):
        sync_step_by_name_result = await self.sync_step_by_name(self.sync_input)
        specific_sync_step_result = await self.specific_sync_step(self.sync_input)
        sync_function_by_function_name_result = await self.sync_function_by_function_name(self.sync_input)

        self.assertEqual(sync_step_by_name_result, self.expected_sync_result)
        self.assertEqual(sync_step_by_name_result, sync_function_by_function_name_result)
        self.assertEqual(specific_sync_step_result, sync_function_by_function_name_result)

        async_step_result = await self.async_step(self.async_input)
        async_function_by_function_name_result = await self.async_function_by_function_name(self.async_input)
        async_step_by_name_result = await self.async_step_by_name(self.async_input)

        self.assertEqual(async_step_result, self.expected_async_result)
        self.assertEqual(async_step_result, async_function_by_function_name_result)
        self.assertEqual(async_step_by_name_result, async_function_by_function_name_result)