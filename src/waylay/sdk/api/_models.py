from __future__ import annotations
from abc import ABC
from datetime import date, datetime
from decimal import Decimal
from inspect import isclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Union, get_type_hints

from typing_extensions import (
    Annotated,  # >=3.9
    Self,  # >=3.12
    TypeAliasType,  # >=3.12
)

if TYPE_CHECKING:
    from typing_extensions import TypeAlias  # >= Python 3.10

from pydantic import (
    BaseModel as PydanticBaseModel,
    ConfigDict,
    SerializationInfo,
    StrictStr,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.functional_validators import ModelWrapValidatorHandler


class BaseModel(PydanticBaseModel, ABC):
    """Waylay base model class that adds some additional methods to Pydantic's `BaseModel`, including a custom validator and serializer."""

    @model_serializer(mode="wrap")
    def _model_serializer(
        self, handler: Callable, info: SerializationInfo
    ) -> Dict[StrictStr, Any]:
        """The default serializer of the model.

        * Excludes `None` fields that were not set at model initialization.
        """
        model_dict = handler(self, info)
        return {
            k: v
            for k, v in model_dict.items()
            if v is not None or k in self.model_fields_set
        }

    @model_validator(mode="wrap")  # type: ignore[arg-type]
    def _model_validator(
        cls, value: Any, handler: ModelWrapValidatorHandler, info: ValidationInfo
    ):
        """The default validator of the model.

        When validation is called with a `skip_validation=True` context (e.g. `cls.model_validate(data, context={"skip_validation": True})`), the model is constructed without validation.
        Any fields with a `Model` type will be constructed from their dict representation recursively.
        """
        context = info.context or {}
        try:
            return handler(value)
        except ValidationError:
            context = info.context or {}
            if context.get("skip_validation", False):
                model = cls.model_construct(**value)
                if not model.model_fields_set:
                    raise
                for field_name in model.model_fields_set:
                    field_value = getattr(model, field_name)
                    cls.__pydantic_validator__.validate_assignment(
                        model,
                        field_name,
                        field_value,
                        strict=(info.config or {}).get("strict"),
                        context=context,
                    )
                return model
            else:
                raise

    @field_validator("*", mode="wrap")
    def _field_validator(
        cls, value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ):
        """The default field validator of the model.

        When validation is called with a `skip_validation=True` context, the field is assigned without validation.
        If the field is a `Model` type, the model will be constructed from its dict representation recursively.
        """
        context = info.context or {}
        try:
            return handler(value)
        except ValidationError:
            context = info.context or {}
            if context.get("skip_validation", False):
                if info.field_name:
                    field_type = get_type_hints(cls).get(info.field_name, Any)
                    try:
                        config = (
                            ConfigDict(arbitrary_types_allowed=True, strict=False)
                            if not isclass(field_type)
                            or not issubclass(field_type, PydanticBaseModel)
                            else None
                        )
                        return TypeAdapter(field_type, config=config).validate_python(
                            value, strict=False, context=context
                        )
                    except ValidationError:
                        return value
            else:
                raise

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


class _Model(BaseModel):
    """A simple model that allows all additional attributes."""

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
