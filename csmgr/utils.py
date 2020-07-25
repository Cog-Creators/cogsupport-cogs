import itertools
from typing import Callable, Generic, Iterable, Iterator, List, Optional, Tuple, TypeVar

import yarl

_T = TypeVar("_T")


class static_property(Generic[_T]):
    """Static property. @staticmethod decorator is required."""

    def __init__(self, func: Callable[[], _T]) -> None:
        self.func = func

    def __get__(self, instance: Optional[object], owner: type) -> _T:
        return self.func()


def grouper(iterable: Iterable[_T], n: int) -> Iterator[List[_T]]:
    """
    Make an iterator that returns lists of length n or lower
    containing items from passed `iterable`.
    """
    iterator = iter(iterable)
    while True:
        try:
            first_item = next(iterator)
        except StopIteration:
            return
        yield list(itertools.islice(itertools.chain((first_item,), iterator), n))


def parse_repo_url(url: str) -> Tuple[str, str, str]:
    """
    Parses given repo URL and returns 3-tuple of service name, repo owner, and repo name.
    """
    parsed = yarl.URL(url)

    assert isinstance(parsed.host, str), "mypy"
    service_name = parsed.host.rsplit(".", maxsplit=2)[-2]

    repo_owner, repo_name = parsed.parts[1:3]

    return service_name, repo_owner, repo_name
