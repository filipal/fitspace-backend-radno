"""Unit tests for the Avatar data model."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.models.avatar import Avatar


@pytest.fixture
def connection():
    """Return a mock database connection."""
    conn = MagicMock()
    return conn


def test_list_by_user_executes_expected_query(connection):
    rows = [
        {
            "id": 2,
            "user_id": 3,
            "display_name": "Latest",
            "height_cm": Decimal("175.0"),
        },
        {
            "id": 1,
            "user_id": 3,
            "display_name": "Test",
            "height_cm": Decimal("180.0"),
        },
    ]
    expected_query = (
        "SELECT *\n"
        "FROM avatars\n"
        "WHERE user_id = %s\n"
        "ORDER BY created_at DESC, id DESC\n"
        "LIMIT %s OFFSET %s"
    )
    with patch("src.models.avatar.execute_query", return_value=rows) as mock_exec:
        model = Avatar(connection)
        result = model.list_by_user(user_id=3, limit=5, offset=10)

    mock_exec.assert_called_once_with(connection, expected_query, (3, 5, 10))
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    assert result == [
        {
            "id": 2,
            "user_id": 3,
            "display_name": "Latest",
            "height_cm": 175.0,
        },
        {
            "id": 1,
            "user_id": 3,
            "display_name": "Test",
            "height_cm": 180.0,
        },
    ]


def test_get_executes_expected_query(connection):
    rows = [
        {"id": 7, "user_id": 2, "display_name": "Primary"}
    ]
    with patch("src.models.avatar.execute_query", return_value=rows) as mock_exec:
        model = Avatar(connection)
        result = model.get(avatar_id=7)

    mock_exec.assert_called_once_with(
        connection,
        "SELECT * FROM avatars WHERE id = %s",
        (7,),
    )
    connection.commit.assert_called_once()
    assert result == rows[0]


def test_get_returns_none_when_no_rows(connection):
    with patch("src.models.avatar.execute_query", return_value=[]) as mock_exec:
        model = Avatar(connection)
        result = model.get(avatar_id=42)

    mock_exec.assert_called_once_with(
        connection,
        "SELECT * FROM avatars WHERE id = %s",
        (42,),
    )
    connection.commit.assert_called_once()
    assert result is None


def test_create_executes_expected_insert(connection):
    payload = {"user_id": 1, "display_name": "New", "age": 30}
    rows = [
        {"id": 9, **payload}
    ]
    expected_query = (
        "INSERT INTO avatars (user_id, display_name, age) "
        "VALUES (%s, %s, %s) RETURNING *"
    )
    with patch("src.models.avatar.execute_query", return_value=rows) as mock_exec:
        model = Avatar(connection)
        result = model.create(**payload)

    mock_exec.assert_called_once_with(connection, expected_query, (1, "New", 30))
    connection.commit.assert_called_once()
    assert result == rows[0]


def test_update_partial_executes_expected_update(connection):
    rows = [
        {"id": 5, "weight_kg": 70.0, "notes": "updated"}
    ]
    expected_query = (
        "UPDATE avatars SET weight_kg = %s, notes = %s, updated_at = NOW() "
        "WHERE id = %s RETURNING *"
    )
    with patch("src.models.avatar.execute_query", return_value=rows) as mock_exec:
        model = Avatar(connection)
        result = model.update_partial(5, weight_kg=70.0, notes="updated")

    mock_exec.assert_called_once_with(
        connection,
        expected_query,
        (70.0, "updated", 5),
    )
    connection.commit.assert_called_once()
    assert result == rows[0]


def test_update_partial_without_fields_raises_value_error(connection):
    model = Avatar(connection)
    with pytest.raises(ValueError):
        model.update_partial(1)
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_delete_executes_expected_delete(connection):
    rows = [{"id": 4}]
    with patch("src.models.avatar.execute_query", return_value=rows) as mock_exec:
        model = Avatar(connection)
        result = model.delete(avatar_id=4)

    mock_exec.assert_called_once_with(
        connection,
        "DELETE FROM avatars WHERE id = %s RETURNING id",
        (4,),
    )
    connection.commit.assert_called_once()
    assert result is True


def test_delete_returns_false_when_no_rows(connection):
    with patch("src.models.avatar.execute_query", return_value=[]) as mock_exec:
        model = Avatar(connection)
        result = model.delete(avatar_id=10)

    mock_exec.assert_called_once_with(
        connection,
        "DELETE FROM avatars WHERE id = %s RETURNING id",
        (10,),
    )
    connection.commit.assert_called_once()
    assert result is False


def test_create_rolls_back_on_failure(connection):
    with patch("src.models.avatar.execute_query", side_effect=RuntimeError("boom")):
        model = Avatar(connection)
        with pytest.raises(RuntimeError):
            model.create(user_id=1, display_name="Bad")

    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()