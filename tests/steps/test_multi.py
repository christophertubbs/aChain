import typing
import pickle

from unittest import IsolatedAsyncioTestCase

from src.achain.steps import MultipleActionStep


def add_to_dict(dictionary: typing.Dict[str, typing.Any], key: str, value: typing.Any) -> typing.Any:
    dictionary[key] = value


class TestMultipleActionStep(IsolatedAsyncioTestCase):
    async def test_steps(self):
        original_object = {}
        values_to_add = {
            "one": [1, 2, 3],
            "two": [4, 5, 6],
            "three": [7, 8, 9],
            "four": {"1": 1, "2": 2, "3": 3},
        }

        functions = MultipleActionStep(
            functions=[
                {
                    "function": add_to_dict,
                    "kwargs": {
                        "key": key,
                        "value": values
                    }
                }
                for key, values in values_to_add.items()
            ]
        )

        try:
            await functions(original_object)
        except:
            raise

        for key, values in values_to_add.items():
            self.assertIn(key, original_object)
            self.assertEqual(original_object[key], values)

    async def test_pickle(self):
        original_object = {}
        values_to_add = {
            "one": [1, 2, 3],
            "two": [4, 5, 6],
            "three": [7, 8, 9],
            "four": {"1": 1, "2": 2, "3": 3},
        }

        functions = MultipleActionStep(
            functions=[
                {
                    "function": add_to_dict,
                    "kwargs": {
                        "key": key,
                        "value": values
                    }
                }
                for key, values in values_to_add.items()
            ]
        )

        await functions(original_object)

        object_for_pickle = {}
        pickled_steps = pickle.loads(pickle.dumps(functions))

        await pickled_steps(object_for_pickle)

        for key in values_to_add:
            self.assertIn(key, original_object)
            self.assertIn(key, object_for_pickle)
            self.assertEqual(original_object[key], object_for_pickle[key])
