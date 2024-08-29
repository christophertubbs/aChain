import sys
import io
import pickle

from unittest import IsolatedAsyncioTestCase

from src.achain.steps import ExceptionStep


def print_error(last_value: int, error: BaseException, file: io.IOBase = sys.stderr) -> int:
    """
    A simple function that might mimic the sort of operation that might handle an error

    :param last_value: The value that was sent into a previous step that encountered an error
    :param error: The error that was thrown
    :param file: Where to write an error message
    :return: The value prior to the error
    """
    print(error, file=file)
    return last_value


def make_step(passthrough_buffer: io.StringIO) -> ExceptionStep[int, int, Exception]:
    return ExceptionStep(
            function=print_error,
            return_on_fail=False,
            kwargs={"file": passthrough_buffer}
        )


class TestExceptionStep(IsolatedAsyncioTestCase):
    async def test_step(self):
        passthrough_buffer = io.StringIO()
        exception = Exception("stuff")
        passthrough_step: ExceptionStep[int, int, Exception] = make_step(passthrough_buffer=passthrough_buffer)
        passthrough_result = await passthrough_step(8, exception)
        passthrough_buffer.seek(0)
        passthrough_text = passthrough_buffer.read().strip()
        self.assertEqual(passthrough_result, 8)
        self.assertEqual(passthrough_text, exception.args[0])

    async def test_pickle(self):
        passthrough_buffer = io.StringIO()
        exception = Exception("stuff")

        passthrough_step: ExceptionStep[int, int, Exception] = make_step(passthrough_buffer=passthrough_buffer)

        pickled_passthrough_step: ExceptionStep[int, int, Exception] = pickle.loads(pickle.dumps(passthrough_step))

        passthrough_result = await passthrough_step(8, exception)
        passthrough_buffer.seek(0)
        passthrough_text = passthrough_buffer.read().strip()

        pickled_passthrough_result = await pickled_passthrough_step(8, exception)
        pickled_passthrough_buffer = pickled_passthrough_step.kwargs['file']
        pickled_passthrough_buffer.seek(0)
        pickled_passthrough_text = pickled_passthrough_buffer.read().strip()

        self.assertEqual(passthrough_result, pickled_passthrough_result)
        self.assertEqual(passthrough_text, pickled_passthrough_text)
