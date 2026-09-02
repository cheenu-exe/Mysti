"""Tests for memory category management."""

import pytest

from mysti.exceptions import ValidationError
from mysti.memory.categories import DEFAULT_CATEGORIES, CategoryManager
from mysti.memory.service import MemoryService


@pytest.fixture
async def categories(memory: MemoryService, keys, storage, audit) -> CategoryManager:
    return CategoryManager(memory, keys, storage, audit)


async def store_one(memory: MemoryService, category: str, content: str):
    return await memory.store(category, content, source="test")


async def test_defaults_present(categories: CategoryManager):
    listed = await categories.list_categories()
    names = {item["name"] for item in listed}
    assert names == set(DEFAULT_CATEGORIES)
    personal = await categories.get_category("personal")
    assert personal["priority"] == 5
    assert "life events" in personal["description"]


async def test_counts_reflect_records(categories: CategoryManager, memory: MemoryService):
    await store_one(memory, "personal", "I prefer tea over coffee")
    await store_one(memory, "personal", "Birthday is in March")
    await store_one(memory, "projects", "MYSTI build plan")
    listed = {item["name"]: item["count"] for item in await categories.list_categories()}
    assert listed["personal"] == 2
    assert listed["projects"] == 1
    assert listed["research"] == 0


async def test_create_custom_category(categories: CategoryManager, memory: MemoryService):
    spec = await categories.create_category(
        "fitness", {"description": "Workouts and health", "priority": 11, "tags": ["gym"]}
    )
    assert spec["priority"] == 10  # clamped to 1-10
    assert await categories.get_category("fitness") == spec
    # a wrapped key now exists and records can be stored in the new category
    record = await memory.store("fitness", "Ran 5k today")
    assert record.category == "fitness"
    # config persists across manager instances
    again = CategoryManager(memory, categories._keys, categories._storage, categories._audit)
    assert (await again.get_category("fitness"))["description"] == "Workouts and health"


async def test_create_duplicate_rejected(categories: CategoryManager):
    with pytest.raises(ValidationError):
        await categories.create_category("personal", {})
    with pytest.raises(ValidationError):
        await categories.create_category("", {})


async def test_delete_category(categories: CategoryManager, memory: MemoryService):
    await categories.create_category("temp", {"description": "scratch"})
    with pytest.raises(ValidationError):
        await categories.delete_category("personal")  # defaults are protected
    with pytest.raises(ValidationError):
        await categories.delete_category("does-not-exist")
    await store_one(memory, "temp", "occupied")
    with pytest.raises(ValidationError):
        await categories.delete_category("temp")  # non-empty refused
    record = (await memory.entries("temp"))[0]
    await memory.delete(record.id)
    await categories.delete_category("temp")
    with pytest.raises(ValidationError):
        await categories.get_category("temp")


async def test_stats(categories: CategoryManager, memory: MemoryService):
    await store_one(memory, "technical", "Docker layer caching explained")
    await store_one(memory, "technical", "numpy broadcasting rules")
    stats = await categories.get_stats()
    assert stats["total_records"] == 2
    tech = stats["categories"]["technical"]
    assert tech["count"] == 2
    assert tech["bytes"] > 0
    assert tech["avg_importance"] == 5
    assert tech["priority"] == 6
