from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Union

from typing_extensions import (
    Annotated,  # >=3.9
    Self,  # >=3.12
    TypeAliasType,  # >=3.12
)

if TYPE_CHECKING:
    from typing_extensions import TypeAlias  # >= Python 3.10

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    """A simple pydantic model that allows all additional attributes."""

    model_config = ConfigDict(extra="allow")

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)
        for field in self.model_fields_set:  # pylint: disable=not-an-iterable
            setattr(
                self, field, _Model.__model_construct_recursive(getattr(self, field))
            )

    @classmethod
    def __model_construct_recursive(cls, obj: Any):
        if isinstance(obj, list):
            return [cls.__model_construct_recursive(inner) for inner in obj]
        elif isinstance(obj, dict):
            model = _Model(**obj)
            return model
        else:
            return obj

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model instance to dict."""
        return self.model_dump()

    def to_json(self) -> str:
        """Convert the model instance to a JSON-encoded string."""
        return self.model_dump_json()

    @classmethod
    def from_dict(cls, obj: dict) -> Self:
        """Create a model instance from a dict."""
        return cls.model_validate(obj)

    @classmethod
    def from_json(cls, json_data: str | bytes | bytearray) -> Self:
        """Create a model instance from a JSON-encoded string."""
        return cls.model_validate_json(json_data)


Primitive: TypeAlias = Union[
    str, bool, int, float, Decimal, bytes, datetime, date, object, None
]
Model: TypeAlias = TypeAliasType(  # type: ignore[valid-type]  #(https://github.com/python/mypy/issues/16614)
    "Model",
    Annotated[
        Union[List["Model"], "_Model", Primitive],  # type: ignore[misc,possible cyclic definition]
        "A basic model that acts like a `simpleNamespace`, or a collection over such models.",
    ],
)
