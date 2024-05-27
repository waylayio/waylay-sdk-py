import pytest

from .pet_model import Pet, PetOwner, PetWithAlias


@pytest.fixture
def pet_instance() -> Pet:
    return Pet(
        name="Lord Biscuit, Master of Naps",
        tag="doggo",
        owner=PetOwner(id=123, name="Simon"),
    )


@pytest.fixture
def pet_instance_json(pet_instance: Pet) -> str:
    return pet_instance.model_dump_json(by_alias=True, exclude_unset=True)


@pytest.fixture
def pet_instance_dict(pet_instance: Pet) -> dict:
    return pet_instance.model_dump(by_alias=True, exclude_unset=True)


@pytest.fixture
def pet_with_alias_instance(pet_instance: Pet) -> dict:
    return PetWithAlias(
        name="Lord Biscuit, Master of Naps",
        tag="doggo",
        owner=PetOwner(id=123, name="Simon"),
        id=1,
    )


@pytest.fixture
def pet_with_alias_instance_dict(pet_with_alias_instance: PetWithAlias) -> dict:
    return pet_with_alias_instance.to_dict()


@pytest.fixture
def pet_list_instance_dict(pet_instance: Pet) -> dict:
    return {
        "pets": [
            pet_instance.model_dump(by_alias=True),
            pet_instance.model_dump(by_alias=True, exclude_unset=True),
        ]
    }
