from typing import Callable, Generic, Optional, TypeVar

_T = TypeVar("_T")


class static_property(Generic[_T]):
    """Static property. @staticmethod decorator is required."""

    def __init__(self, func: Callable[[], _T]) -> None:
        self.func = func

    def __get__(self, instance: Optional[object], owner: type) -> _T:
        return self.func()
