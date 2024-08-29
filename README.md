# aChain
Library used for chaining together synchronous and asynchronous functions for data transformation


## What does this do?

The `achain.Chain` class allows for the construction of chained synchronous and asynchronous functions

## Example:

```python
import typing
import json
from datetime import datetime, timedelta

from achain import Chain

SERVICE_URL = "https://www.service.com/api"
"""The address of some service containing data of interest"""

async def get_data(url, **kwargs) -> str:
    """
    Gets raw text from the given URL with the given query parameters
    """
    ...

def normalize_data(
    data: typing.Dict[str, typing.Any]
) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
    """
    Transforms the passed data into one that is easier to deserialize
    """
    ...

class ExampleClass:
    """
    An example of a class that may be constructed from the generated data
    """
    def __init__(self, **kwargs):
        """Constructor"""
        ...

async def main():
    """
    Create lists of remote data
    """
    # Declare your chain
    chain: Chain[typing.List[ExampleClass]] = Chain(
        get_data,
        url=SERVICE_URL
    ).then(
        json.loads
    ).then(
        normalize_data
    ).then(
        lambda data: [ExampleClass(**values) for values in data.values()]
    )
    
    # Call Asynchronously
    yesterdays_data: typing.List[ExampleClass] = await chain(
        start=datetime.now() - timedelta(hours=48),
        end=datetime.now() - timedelta(hours=24)
    )

    # Call Synchronously
    todays_data: typing.List[ExampleClass] = chain.execute_synchronously(
        start=datetime.now() - timedelta(hours=24),
        end=datetime.now
    )
```