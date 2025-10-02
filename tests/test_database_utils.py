"""Tests for database utility helpers."""
from unittest.mock import MagicMock

import pytest

from src.utils.database import execute_query


def _make_cursor(*, description=None, rows=None, rowcount=0, execute_side_effect=None):
    cursor = MagicMock()
    cursor.description = description
    cursor.fetchall.return_value = rows or []
    cursor.rowcount = rowcount
    cursor.execute.side_effect = execute_side_effect
    return cursor


def _make_connection(cursor):
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection


@pytest.mark.parametrize(
    "query,description,rows",
    [
        (
            "INSERT INTO avatars (user_id, display_name) VALUES (%s, %s) RETURNING id",
            [("id", None, None, None, None, None, None)],
            [(1,)],
        ),
        (
            "UPDATE avatars SET display_name = %s WHERE id = %s RETURNING id, display_name",
            [
                ("id", None, None, None, None, None, None),
                ("display_name", None, None, None, None, None, None),
            ],
            [(5, "Updated")],
        ),
        (
            "DELETE FROM avatars WHERE id = %s RETURNING id",
            [("id", None, None, None, None, None, None)],
            [(7,)],
        ),
    ],
)
def test_execute_query_fetches_rows_for_returning_statements(query, description, rows):
    """Statements that RETURN rows should yield dictionaries."""
    cursor = _make_cursor(description=description, rows=rows, rowcount=len(rows))
    connection = _make_connection(cursor)

    result = execute_query(connection, query, params=(1, 2))

    expected = [dict(zip([column[0] for column in description], row)) for row in rows]
    assert result == expected
    cursor.fetchall.assert_called_once()
    connection.commit.assert_not_called()


def test_execute_query_returns_rowcount_when_no_result_set():
    """Non-returning statements should expose rowcount when fetching."""
    cursor = _make_cursor(description=None, rows=[], rowcount=3)
    connection = _make_connection(cursor)

    result = execute_query(connection, "UPDATE avatars SET display_name = %s WHERE id = %s", params=("A", 1))

    assert result == 3
    cursor.fetchall.assert_not_called()


def test_execute_query_commit_and_rowcount_when_fetch_false():
    """When fetch is False the helper should commit and return the rowcount."""
    cursor = _make_cursor(description=None, rows=[], rowcount=2)
    connection = _make_connection(cursor)

    result = execute_query(
        connection,
        "DELETE FROM avatars WHERE id = %s",
        params=(1,),
        fetch=False,
    )

    assert result == 2
    cursor.fetchall.assert_not_called()
    connection.commit.assert_called_once()