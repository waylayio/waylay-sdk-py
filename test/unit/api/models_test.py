"""Test suite for waylay.sdk.api._models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from .example.pet_model import Pet

if TYPE_CHECKING:
    from typing import TypeAlias


PetTypeAlias: TypeAlias = Pet | list[Pet]


def test_validate_single_model_from_union():
    """Test TypeAdapter validates single model from union correctly."""
    adapter = TypeAdapter(PetTypeAlias)

    pet_data = {
        "name": "Chop",
        "owner": {"id": 123, "name": "Simon"},
        "tag": "doggo",
    }

    result = adapter.validate_python(pet_data)

    assert isinstance(result, Pet)
    assert result.name == "Chop"
    assert result.tag == "doggo"
    assert result.owner.id == 123
    assert result.owner.name == "Simon"


def test_validate_list_from_union():
    """Test that list type in union is correctly selected and validated."""
    adapter = TypeAdapter(PetTypeAlias)

    list_data = [
        {"name": "Chop", "owner": {"id": 123, "name": "Simon"}},
        {"name": "Peanut", "owner": {"id": 456, "name": "Alex"}},
        {"name": "Pumpkin", "owner": {"id": 789, "name": "Taylor"}},
    ]

    result = adapter.validate_python(list_data)

    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(pet, Pet) for pet in result)
    assert result[0].name == "Chop"
    assert result[1].name == "Peanut"
    assert result[2].name == "Pumpkin"


def test_skip_validation_incomplete_single_model():
    """Test skip_validation handles incomplete data for single model."""
    adapter = TypeAdapter(PetTypeAlias)

    incomplete_data = {
        "name": "Chop",
    }

    result = adapter.validate_python(incomplete_data, context={"skip_validation": True})

    assert isinstance(result, Pet)
    assert result.name == "Chop"
    assert result.owner is None
    assert result.tag is None


def test_skip_validation_invalid_types_single_model():
    """Test skip_validation handles invalid types for single model."""
    adapter = TypeAdapter(PetTypeAlias)

    invalid_data = {
        "name": 123,
        "owner": {"id": "not_an_int", "name": "Simon"},
    }

    result = adapter.validate_python(invalid_data, context={"skip_validation": True})

    assert isinstance(result, Pet)
    assert result.name == 123
    assert result.owner.id == "not_an_int"
    assert result.owner.name == "Simon"


def test_skip_validation_incomplete_list_models():
    """Test skip_validation handles list with incomplete model data."""
    adapter = TypeAdapter(PetTypeAlias)

    list_data = [
        {"name": "Chop"},
        {"name": "Peanut", "owner": {"id": 456, "name": "Alex"}},
        {"owner": {"id": 789, "name": "Taylor"}},
    ]

    result = adapter.validate_python(list_data, context={"skip_validation": True})

    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(pet, Pet) for pet in result)
    assert result[0].name == "Chop"
    assert result[0].owner is None
    assert result[1].name == "Peanut"
    assert result[1].owner.name == "Alex"
    assert result[2].name is None
    assert result[2].owner.name == "Taylor"


def test_skip_validation_invalid_types_list_models():
    """Test skip_validation handles list with invalid types in model data."""
    adapter = TypeAdapter(PetTypeAlias)

    list_data = [
        {"name": 123, "owner": {"id": "invalid", "name": "Simon"}},
        {"name": "Peanut", "owner": {"id": 456, "name": 789}},
    ]

    result = adapter.validate_python(list_data, context={"skip_validation": True})

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].name == 123
    assert result[0].owner.id == "invalid"
    assert result[1].name == "Peanut"
    assert result[1].owner.name == 789


def test_skip_validation_with_empty_dict():
    """Test skip_validation constructs model with all required fields set to None."""
    adapter = TypeAdapter(PetTypeAlias)

    result = adapter.validate_python({}, context={"skip_validation": True})

    assert isinstance(result, Pet)
    assert result.name is None
    assert result.owner is None
    assert result.tag is None


def test_skip_validation_preserves_extra_fields_with_invalid_data():
    """Test skip_validation preserves extra fields when validation fails."""
    adapter = TypeAdapter(PetTypeAlias)

    # Invalid data (missing owner) with extra fields
    invalid_data_with_extra = {
        "name": "Chop",
        "extra_field": "should_be_preserved",
        "another_extra": 999,
    }

    result = adapter.validate_python(
        invalid_data_with_extra, context={"skip_validation": True}
    )

    assert isinstance(result, Pet)
    assert result.name == "Chop"
    assert result.owner is None
    assert hasattr(result, "__pydantic_extra__")
    assert result.__pydantic_extra__ == {
        "extra_field": "should_be_preserved",
        "another_extra": 999,
    }


def test_skip_validation_handles_nested_incomplete_models():
    """Test skip_validation propagates context to nested model construction."""
    adapter = TypeAdapter(PetTypeAlias)

    nested_incomplete = {
        "name": "Chop",
        "owner": {"name": "Simon"},
    }

    result = adapter.validate_python(
        nested_incomplete, context={"skip_validation": True}
    )

    assert isinstance(result, Pet)
    assert result.name == "Chop"
    assert result.owner.name == "Simon"
    assert result.owner.id is None


def test_explicit_none_preserves_field_in_fields_set():
    """Test that explicitly passing None marks field as set, unlike missing field."""
    adapter = TypeAdapter(PetTypeAlias)

    with_explicit_none = {
        "name": "Chop",
        "owner": {"id": 123, "name": "Simon"},
        "tag": None,
    }

    result = adapter.validate_python(with_explicit_none)

    assert isinstance(result, Pet)
    assert result.name == "Chop"
    assert result.tag is None
    assert "tag" in result.model_fields_set
    assert "name" in result.model_fields_set


def test_missing_optional_field_not_in_fields_set():
    """Test that missing optional field is not in model_fields_set."""
    adapter = TypeAdapter(PetTypeAlias)

    without_tag = {
        "name": "Chop",
        "owner": {"id": 123, "name": "Simon"},
    }

    result = adapter.validate_python(without_tag)

    assert isinstance(result, Pet)
    assert result.tag is None
    assert "tag" not in result.model_fields_set
    assert "name" in result.model_fields_set
