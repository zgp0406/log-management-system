from __future__ import annotations

from typing import Any, Iterable, Iterator, List, Sequence


class QuerySetStub(Sequence[Any]):
    """
    Lightweight stand-in for Django QuerySets used in unit tests.

    It implements the subset of methods exercised in the project code so that we
    can unit-test view logic without requiring a real database.
    """

    def __init__(self, items: Iterable[Any] | None = None) -> None:
        self._items: List[Any] = list(items or [])

    # --- Sequence protocol -------------------------------------------------
    def __iter__(self) -> Iterator[Any]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> Any:
        return self._items[index]

    # --- QuerySet-like helpers ---------------------------------------------
    def _clone(self, items: Iterable[Any] | None = None) -> "QuerySetStub":
        return QuerySetStub(items if items is not None else self._items)

    def all(self, *args: Any, **kwargs: Any) -> "QuerySetStub":
        return self._clone()

    def filter(self, *args: Any, **kwargs: Any) -> "QuerySetStub":
        items = self._items
        for key, expected in kwargs.items():
            attr_path, lookup = self._split_lookup(key)
            filtered = []
            for item in items:
                value = self._resolve_attr(item, attr_path)
                if self._matches_lookup(value, lookup, expected):
                    filtered.append(item)
            items = filtered
        return QuerySetStub(items)

    def exclude(self, *args: Any, **kwargs: Any) -> "QuerySetStub":
        included = self.filter(*args, **kwargs)
        excluded_ids = {id(item) for item in included}
        remaining = [item for item in self._items if id(item) not in excluded_ids]
        return QuerySetStub(remaining)

    def select_related(self, *args: Any, **kwargs: Any) -> "QuerySetStub":
        return self

    def order_by(self, *args: Any, **kwargs: Any) -> "QuerySetStub":
        return self._clone()

    def values(self, *fields: str) -> List[dict[str, Any]]:
        results: List[dict[str, Any]] = []
        for item in self._items:
            results.append({field: getattr(item, field) for field in fields})
        return results

    def values_list(self, field: str, flat: bool = False) -> List[Any]:
        values = [getattr(item, field) for item in self._items]
        return values if flat else [(value,) for value in values]

    def first(self) -> Any:
        return self._items[0] if self._items else None

    def count(self) -> int:
        return len(self._items)

    def exists(self) -> bool:
        return bool(self._items)

    def none(self) -> "QuerySetStub":
        return QuerySetStub()

    def get(self, **kwargs: Any) -> Any:
        if not self._items:
            raise LookupError("QuerySetStub is empty")
        return self._items[0]

    def update(self, **kwargs: Any) -> None:
        for item in self._items:
            for key, value in kwargs.items():
                setattr(item, key, value)

    def delete(self) -> None:
        self._items.clear()

    # --- Internal helpers --------------------------------------------------
    @staticmethod
    def _split_lookup(key: str) -> tuple[str, str]:
        known_lookups = {"in", "isnull", "icontains", "contains", "date", "lt", "gt", "lte", "gte"}
        parts = key.split("__")
        if parts[-1] in known_lookups:
            return "__".join(parts[:-1]), parts[-1]
        return key, "exact"

    @staticmethod
    def _resolve_attr(item: Any, path: str) -> Any:
        value = item
        if not path:
            return value
        for part in path.split("__"):
            if value is None:
                return None
            value = getattr(value, part, None)
        return value

    @staticmethod
    def _matches_lookup(value: Any, lookup: str, expected: Any) -> bool:
        if lookup == "exact":
            return value == expected
        if lookup == "isnull":
            return (value is None) == bool(expected)
        if lookup == "in":
            return value in expected
        if lookup == "icontains":
            value_str = (value or "").lower()
            return str(expected).lower() in value_str
        if lookup == "contains":
            value_str = value or ""
            return str(expected) in value_str
        if lookup == "date":
            if value is None:
                return expected is None
            if hasattr(value, "date"):
                return value.date() == expected
            return value == expected
        if lookup == "lt":
            return value is not None and value < expected
        if lookup == "gt":
            return value is not None and value > expected
        if lookup == "lte":
            return value is not None and value <= expected
        if lookup == "gte":
            return value is not None and value >= expected
        return True

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"QuerySetStub({self._items!r})"

