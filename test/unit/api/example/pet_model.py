from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Union

from pydantic import Field, StrictBool, StrictInt, StrictStr
from typing_extensions import NotRequired, TypedDict

from waylay.sdk.api._models import BaseModel


class PetList(BaseModel):
    """Pet List."""

    pets: List[Pet]

    model_config = {
        "populate_by_name": True,
        "protected_namespaces": (),
    }


class Pet(BaseModel):
    """Pet."""

    name: StrictStr
    owner: PetOwner
    tag: StrictStr | None = None

    model_config = {
        "populate_by_name": True,
        "protected_namespaces": (),
    }


class PetOwner(BaseModel):
    """Owner."""

    id: StrictInt
    name: StrictStr

    model_config = {
        "populate_by_name": True,
        "protected_namespaces": (),
    }


PetUnion = Union[PetList, Pet]


class PetType(str, Enum):
    """Pet Type."""

    DOG = "dog"
    CAT = "cat"


class PetWithAlias(Pet):
    """Pet with alias field."""

    id: StrictInt = Field(alias="pet_id")

    model_config = {
        "populate_by_name": True,
        "protected_namespaces": (),
    }


class CreatePetQuery(TypedDict):
    """create_pet query parameters."""

    limit: NotRequired[
        Annotated[
            Annotated[int, Field(le=100, strict=True)] | None,
            Field(description="How many biscuits?"),
        ]
    ]
    good_boy: NotRequired[
        Annotated[StrictBool | None, Field(description="Is the pet a good boy?")]
    ]
