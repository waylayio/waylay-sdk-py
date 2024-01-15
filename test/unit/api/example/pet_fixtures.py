import pytest

from .pet_model import PetOwner, Pet


@pytest.fixture
def pet_instance() -> Pet:
    return Pet(name='Lord Biscuit, Master of Naps', tag='doggo', owner=PetOwner(id=123, name='Simon'))


@pytest.fixture
def pet_instance_json(pet_instance) -> str:
    return pet_instance.to_json()


@pytest.fixture
def pet_instance_dict(pet_instance) -> dict:
    return pet_instance.to_dict()
