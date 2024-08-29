import pickle

from unittest import IsolatedAsyncioTestCase

from src.achain.steps import ConditionalStep
from src.achain.steps import Function


def predicate(value: int, *args, **kwargs) -> bool:
    return (value + sum(args) + sum(value for value in kwargs.values())) % 2 == 0


def on_true(value: int, *args, **kwargs) -> float:
    return (value + sum(args) + sum(value for value in kwargs.values())) / 2.0


def on_false(value: int, *args, **kwargs) -> str:
    return str((value + sum(args) + sum(value for value in kwargs.values())))


class TestConditionalStep(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.true_function = on_true
        self.false_function = on_false
        self.predicate = predicate

    async def test_only_true(self):
        step = ConditionalStep(
            predicate=self.predicate,
            true_function={
                "function": self.true_function,
                "args": (1, 2, 3),
                "kwargs": {
                    "one": 1,
                    "two": 2,
                    "three": 3,
                }
            },
        )

        failing_input = 1
        passing_input = 2

        self.assertTrue(await step(failing_input), failing_input)
        self.assertEqual(await step(passing_input), 7.0)

    async def test_only_false(self):
        step = ConditionalStep(
            predicate=self.predicate,
            false_function={
                "function": f"{self.__class__.__module__}.on_false",
                "args": (1, 2, 3),
                "kwargs": {
                    "one": 1,
                    "two": 2,
                    "three": 3,
                }
            },
        )

        failing_input = 1
        passing_input = 2

        self.assertTrue(await step(failing_input), "13")
        self.assertEqual(await step(passing_input), passing_input)

    async def test_with_true_and_false(self):
        step = ConditionalStep(
            predicate=self.predicate,
            true_function=Function(
                function=self.true_function,
                args=(1, 2, 3),
                kwargs={"one": 1, "two": 2, "three": 3}
            ),
            false_function={
                "function": f"{self.__class__.__module__}.on_false",
                "args": (1, 2, 3),
                "kwargs": {
                    "one": 1,
                    "two": 2,
                    "three": 3,
                }
            },
        )

        failing_input = 1
        passing_input = 2

        self.assertTrue(await step(failing_input), "13")
        self.assertEqual(await step(passing_input), 7.0)

    async def test_pickling(self):
        step = ConditionalStep(
            predicate=predicate,
            true_function=Function(
                function=self.true_function,
                args=(1, 2, 3),
                kwargs={"one": 1, "two": 2, "three": 3}
            ),
            false_function={
                "function": f"{self.__class__.__module__}.on_false",
                "args": (1, 2, 3),
                "kwargs": {
                    "one": 1,
                    "two": 2,
                    "three": 3,
                }
            },
        )

        failing_input = 1
        passing_input = 2

        pickled_step = pickle.loads(pickle.dumps(step))

        self.assertEqual(await step(failing_input), await pickled_step(failing_input))
        self.assertEqual(await step(passing_input), await pickled_step(passing_input))
