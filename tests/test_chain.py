import logging
from unittest import IsolatedAsyncioTestCase

import typing
import json
import inspect
import pickle

from functools import reduce
from functools import singledispatch
from urllib import request
from http.client import HTTPResponse
from datetime import datetime

import math

from src.achain import Chain
from src.achain.steps import call

Collection = typing.Union[typing.MutableMapping, typing.MutableSequence]
Key = typing.Union[str, int]

NWIS_URL = "https://waterservices.usgs.gov/nwis/iv/"
FORMAT = "json"
STATE_CODE = "al"
INDENT = "on"
SITE_STATUS = "active"
SITE_TYPE = "ST"
PERIOD = "PT30M"

DATE_FORMAT: typing.Final[str] = "%Y-%m-%dT%H:%M:%S.%f%z"

logging.getLogger('asyncio').setLevel(logging.WARNING)

def get_data(**kwargs) -> str:
    query: str = "&".join(f"{key.strip()}={value.strip()}" for key, value in kwargs.items())

    if query:
        url = f"{NWIS_URL}?{query}"
    else:
        url = NWIS_URL

    req = request.Request(url=url)

    with request.urlopen(req) as response:    # type: HTTPResponse
        return response.read().decode()


@singledispatch
async def operate_on_collection(
    collection: Collection,
    operation: typing.Callable[[Collection, Key], typing.Any],
    *paths: str,
    condition: typing.Callable[[Collection, Key], bool] = None,
    separate_path: typing.Callable[[str], typing.List[str]] = lambda path: path.split("/")
) -> Collection:
    raise NotImplementedError(
        f"There is not an implementation for 'operate_on_collection' that takes the following values: "
        f"collection (type={type(collection)}), "
        f"operation (type={type(operation)}), "
        f"paths (type={type(paths)}), "
        f"condition (type={type(condition)}), "
        f"separate_path (type={type(separate_path)}). "
    )


@operate_on_collection.register
async def _(
    collection: list,
    operation: typing.Callable[[typing.MutableSequence, int], typing.Any],
    *paths: str,
    condition: typing.Callable[[typing.MutableSequence, int], bool] = None,
    separate_path: typing.Callable[[str], typing.List[str]] = lambda path: path.split("/")
) -> list:
    if not paths:
        return collection

    traversal_paths: typing.List[str] = reduce(
        lambda first_collection, second_collection: first_collection + second_collection,
        [[part.strip() for part in separate_path(path) if part.strip()] for path in paths]
    )

    current_path = traversal_paths[0]
    remaining_paths = traversal_paths[1:]

    if current_path == "*":
        for index in range(len(collection) - 1, -1, -1):
            if remaining_paths and isinstance(collection[index], (typing.Mapping, typing.Sequence)):
                await operate_on_collection(collection[index], operation, *remaining_paths, condition=condition)
            elif not condition or condition(collection, index):
                operation_result = operation(collection, index)
                while inspect.isawaitable(operation_result):
                    operation_result = await operation_result
    elif current_path.isdigit():
        index = int(current_path)
        if 0 <= index < len(collection):
            if remaining_paths and isinstance(collection[index], (typing.Mapping, typing.Sequence)):
                await operate_on_collection(collection[index], operation, *remaining_paths, condition=condition)
            elif not condition or condition(collection, index):
                operation_result = operation(collection, index)

                while inspect.isawaitable(operation_result):
                    operation_result = await operation_result

    return collection


@operate_on_collection.register
async def _(
    collection: dict,
    operation: typing.Callable[[typing.MutableMapping, str], typing.Any],
    *paths: str,
    condition: typing.Callable[[typing.MutableMapping, str], bool] = None,
    separate_path: typing.Callable[[str], typing.List[str]] = lambda path: path.split("/")
) -> dict:
    if not paths:
        return collection

    traversal_paths: typing.List[str] = reduce(
        lambda first_collection, second_collection: first_collection + second_collection,
        [[part.strip() for part in separate_path(path) if part.strip()] for path in paths]
    )

    current_path = traversal_paths[0]
    remaining_paths = traversal_paths[1:]

    if current_path == "*":
        for key in list(collection.keys()):
            await operate_on_collection(collection[key], operation, *remaining_paths, condition=condition)
            if not remaining_paths and (not condition or condition(collection, key)):
                operation_result = operation(collection, key)
                while inspect.isawaitable(operation_result):
                    operation_result = await operation_result
    elif current_path in collection:
        next_value = collection[current_path]
        if remaining_paths and isinstance(next_value, (typing.MutableMapping, typing.MutableSequence)) and not isinstance(next_value, str):
            await operate_on_collection(next_value, operation, *remaining_paths, condition=condition)
        elif not condition or condition(collection, current_path):
            operation_result = operation(collection, current_path)
            while inspect.isawaitable(operation_result):
                operation_result = await operation_result

    return collection


def is_non_streamflow_timeseries(container: typing.Dict[str, typing.Any], key: str) -> bool:
    """
    Determines if the value belonging at the key in the given container is a non-streamflow timeseries.

    Args:
        container: The collection that contains a value at the given key
        key: The key to check

    Returns:
        True if the value at the key in the given container is a time series that isn't streamflow
    """
    value = container[key]

    if not isinstance(value, dict):
        return False

    if not isinstance(value.get("sourceInfo"), typing.Mapping):
        return False

    if not isinstance(value.get("variable"), dict):
        return False

    if not isinstance(value.get("name"), str):
        return False

    if not isinstance(value.get("values"), typing.MutableSequence):
        return False

    variable_data: dict = value.get("variable")
    variable_code = variable_data.get("variableCode")
    if not variable_code or not isinstance(variable_code, typing.Sequence):
        return False

    code = variable_code[0]
    return code.get("value") != "00060"


def remove_key(container: typing.Dict[str, typing.Any], key: str) -> typing.Any:
    container.pop(key)


def format_datetimes(container: typing.Dict[str, typing.Any], key: str) -> typing.Any:
    container[key] = datetime.strptime(container[key], DATE_FORMAT)


def assign_usgs_names(timeseries: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Dict[str, typing.Any]]:
    for series in timeseries:
        series['siteName'] = series['sourceInfo']['siteName']
        series['site'] = series['sourceInfo']['siteCode'][0]['value']
        del series['sourceInfo']
    return timeseries


async def assign_variable(timeseries: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Dict[str, typing.Any]]:
    for series in timeseries:
        series['variableName'] = series['variable']['variableName']
        series['variable'] = series['variable']['variableCode'][0]['value']

    return timeseries


async def print_info(value: typing.Any, text: str) -> typing.Any:
    print(text)
    return value


async def format_values(timeseries: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Dict[str, typing.Any]]:
    def convert_to_float(container: typing.MutableMapping, key: str) -> typing.Any:
        try:
            container[key] = float(container[key])
        except:
            container[key] = math.nan

    for series in timeseries:
        await operate_on_collection(series, convert_to_float, "values/*/value/*/value")

    return timeseries


async def flatten_values(timeseries: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Dict[str, typing.Any]]:
    for series in timeseries:
        series['values'] = series['values'][0]['value']
    return timeseries


async def map_timeseries_to_name(
    timeseries: typing.List[typing.Dict[str, typing.Any]]
) -> typing.MutableMapping[str, typing.Dict[str, typing.Any]]:
    mapped_timeseries = {}

    for series in timeseries:
        if 'site' not in series:
            raise KeyError(
                f"The 'site' value is missing from this time series. Available keys are: {', '.join(series.keys())}"
            )
        mapped_timeseries[series['site']] = series

    return mapped_timeseries


def convert_nwis_data_to_timeseries(nwis_data: typing.MutableMapping[str, typing.Any]) -> typing.List[typing.Dict[str, typing.Any]]:
    return nwis_data['value']['timeSeries']


def throw_error(value: typing.Any, *args, **kwargs) -> typing.NoReturn:
    raise Exception("This was meant to be thrown to test exceptions")


def handle_error(value: typing.Any, error: BaseException, *args, **kwargs) -> int:
    return 15


def make_chain() -> Chain[typing.Dict[str, typing.Dict[str, typing.Any]]]:
    return Chain(
            get_data,
            kwargs={
                "stateCd": STATE_CODE,
                "siteType": SITE_TYPE,
                "period": PERIOD,
                "format": FORMAT,
                "siteStatus": SITE_STATUS
            }
        ).then(
            json.loads
        ).then(
            operate_on_collection,
            remove_key,
            "value/timeSeries/*",
            condition=is_non_streamflow_timeseries
        ).all(
            call(operate_on_collection, remove_key, "value/timeSeries/*/values/*/value/*/qualifiers"),
            call(operate_on_collection, format_datetimes, "value/timeSeries/*/values/*/value/*/dateTime")
        ).then(
            convert_nwis_data_to_timeseries
        ).all(
            assign_usgs_names,
            assign_variable,
            format_values
        ).then(
            flatten_values
        ).then(
            map_timeseries_to_name
        )


class TestChain(IsolatedAsyncioTestCase):

    def run_full_series_assertions(self, results: typing.Dict[str, typing.Dict[str, typing.Any]]):
        self.assertTrue(isinstance(results, dict))

        for key, value in results.items():
            self.assertTrue(isinstance(key, str))
            self.assertTrue(isinstance(value, dict))
            self.assertTrue(key.isdigit())
            self.assertEqual(len(value), 6)
            self.assertIn("variable", value)
            self.assertIn("siteName", value)
            self.assertIn("values", value)
            self.assertIn("name", value)
            self.assertIn("variableName", value)
            self.assertIn("siteName", value)
            self.assertIn("site", value)
            self.assertEqual(key, value['site'])
            self.assertEqual(
                value['variable'],
                '00060',
                f"Non-streamflow data for site {value['site']} was detected. Found '{value['variableName']}'"
            )

    async def test_one_at_a_time(self):
        chain = Chain(
            get_data,
            kwargs={
                "stateCd": STATE_CODE,
                "siteType": SITE_TYPE,
                "period": PERIOD,
                "format": FORMAT,
                "siteStatus": SITE_STATUS
            }
        )
        chain = chain.then(json.loads)
        chain = chain.then(
            operate_on_collection,
            remove_key,
            "value/timeSeries/*",
            condition=is_non_streamflow_timeseries
        )
        chain = chain.all(
            call(operate_on_collection, remove_key, "value/timeSeries/*/values/*/value/*/qualifiers"),
            call(operate_on_collection, format_datetimes, "value/timeSeries/*/values/*/value/*/dateTime")
        )
        chain = chain.then(convert_nwis_data_to_timeseries)
        chain = chain.all(
            assign_usgs_names,
            assign_variable,
            format_values
        )
        chain = chain.then(flatten_values)
        chain = chain.then(map_timeseries_to_name)
        timeseries_data: typing.Dict[str, typing.Dict[str, typing.Any]] = await chain.execute()

        self.run_full_series_assertions(timeseries_data)

    async def test_full_chain(self):
        timeseries_data: typing.Dict[str, typing.Dict[str, typing.Any]] = await make_chain().execute()
        self.run_full_series_assertions(timeseries_data)

    async def test_then(self):
        original_values: typing.Dict[str, typing.Any] = {
            "one": 1,
            "two": 2,
            "three": 3,
        }
        new_dictionary = await Chain(lambda: original_values).then(json.dumps).then(json.loads)
        self.assertDictEqual(original_values, new_dictionary)

    async def test_all(self):
        def add_to_dict(dictionary: typing.Dict[str, typing.Any], key: str, value: typing.Any) -> typing.Any:
            dictionary[key] = value

        original_object = {}
        values_to_add = {
            "one": [1, 2, 3],
            "two": [4, 5, 6],
            "three": [7, 8, 9],
            "four": {"1": 1, "2": 2, "3": 3},
        }
        await Chain(original_object).all(*[
            call(add_to_dict, key, value)
            for key, value in values_to_add.items()
        ])
        self.assertDictEqual(original_object, values_to_add)

    async def test_exception(self):
        chain = Chain(9)
        chain.then(throw_error)
        chain.exception(handle_error)
        self.assertEqual(15, await chain())

    def test_call_synchronously(self):
        timeseries_data: typing.Dict[str, typing.Dict[str, typing.Any]] = make_chain().execute_synchronously()

        self.run_full_series_assertions(timeseries_data)

    async def test_pickleable(self):
        chain: Chain[typing.Dict[str, typing.Dict[str, typing.Any]]] = make_chain()
        pickled_chain: Chain[typing.Dict[str, typing.Dict[str, typing.Any]]] = pickle.loads(pickle.dumps(chain))
        self.assertTrue(isinstance(pickled_chain._thread_pool, type(chain._thread_pool)))

        pickled_results: typing.Dict[str, typing.Dict[str, typing.Any]] = await pickled_chain()
        self.run_full_series_assertions(pickled_results)
