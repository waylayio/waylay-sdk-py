from __future__ import annotations
from typing import Any, List, Union
from typing_extensions import TypeAliasType
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated  # type: ignore
from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    """A simple pydantic model that allows all additional attributes."""

    model_config = ConfigDict(extra="allow")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for field in self.model_fields_set:  # pylint: disable=not-an-iterable
            setattr(self, field, _Model.__model_construct_recursive(getattr(self, field)))

    @classmethod
    def __model_construct_recursive(cls, obj: Any):
        if isinstance(obj, list):
            return [cls.__model_construct_recursive(inner) for inner in obj]
        elif isinstance(obj, dict):
            model = _Model(**obj)
            return model
        else:
            return obj

    def to_dict(self):
        """Convert model instance to dict."""
        return self.model_dump()


Model = TypeAliasType(
    'Model',
    Annotated[
        Union[List['Model'], '_Model', Any],  # type: ignore[misc,possible cyclic definition]
        "A basic model that acts like a `simpleNamespace`, or a collection over such models.",
    ],
)
