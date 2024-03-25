from __future__ import annotations
from enum import Enum

from typing import List, Optional, Union
from typing_extensions import TypedDict, NotRequired, Annotated
from pydantic import Field, StrictBool, StrictInt, StrictStr

from waylay.sdk.api._models import _BaseModel


class PetList(_BaseModel):
    """Pet List."""

    pets: List[Pet]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }


class Pet(_BaseModel):
    """Pet."""

    name: StrictStr
    owner: PetOwner
    tag: Optional[StrictStr] = None

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }


class PetOwner(_BaseModel):
    """Owner."""

    id: StrictInt
    name: StrictStr

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }


PetUnion = Union[PetList, Pet]


class PetType(str, Enum):
    """Pet Type."""

    DOG = "dog"
    CAT = "cat"


class CreatePetQuery(TypedDict):
    """create_pet query parameters."""

    limit: NotRequired[
        Annotated[
            Optional[Annotated[int, Field(le=100, strict=True)]],
            Field(description="How many biscuits?"),
        ]
    ]
    good_boy: NotRequired[
        Annotated[Optional[StrictBool], Field(description="Is the pet a good boy?")]
    ]
