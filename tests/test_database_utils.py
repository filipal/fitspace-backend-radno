"""Tests for database utility helpers."""
import json
from unittest.mock import MagicMock

import pytest

from src.utils import database

execute_query = database.execute_query


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

def _clear_connection_env(monkeypatch):
    for key in [
        'DB_HOST',
        'DB_NAME',
        'DB_USERNAME',
        'DB_PASSWORD',
        'DB_SECRET_ARN',
        'DB_PROXY_ENDPOINT',
        'DB_CLUSTER_ENDPOINT',
    ]:
        monkeypatch.delenv(key, raising=False)


def _mock_secret_client(monkeypatch, secret_dict):
    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {'SecretString': json.dumps(secret_dict)}
    monkeypatch.setattr(database.boto3, 'client', lambda *args, **kwargs: secrets_client)
    return secrets_client


def _mock_psycopg_connect(monkeypatch):
    connection = MagicMock()
    connect_mock = MagicMock(return_value=connection)
    monkeypatch.setattr(database.psycopg2, 'connect', connect_mock)
    return connect_mock, connection


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


def test_get_database_connection_prefers_cluster_endpoint(monkeypatch):
    """Secrets-based connections should prioritise the cluster endpoint when provided."""
    _clear_connection_env(monkeypatch)
    monkeypatch.setenv('DB_SECRET_ARN', 'arn:secret')
    monkeypatch.setenv('DB_CLUSTER_ENDPOINT', 'cluster.example.com')

    secret = {'username': 'user', 'password': 'pass', 'dbname': 'db', 'port': 5432, 'host': 'secret-host'}
    secrets_client = _mock_secret_client(monkeypatch, secret)
    connect_mock, connection = _mock_psycopg_connect(monkeypatch)

    result = database.get_database_connection()

    connect_mock.assert_called_once_with(
        host='cluster.example.com',
        database='db',
        user='user',
        password='pass',
        port=5432,
        connect_timeout=5,
    )
    secrets_client.get_secret_value.assert_called_once()
    assert result is connection
    assert connection.autocommit is False


def test_get_database_connection_uses_secret_host_when_available(monkeypatch):
    """When the secret includes a host value, it should be used without a proxy."""
    _clear_connection_env(monkeypatch)
    monkeypatch.setenv('DB_SECRET_ARN', 'arn:secret')

    secret = {'username': 'user', 'password': 'pass', 'dbname': 'db', 'port': 5432, 'host': 'secret-host'}
    _mock_secret_client(monkeypatch, secret)
    connect_mock, connection = _mock_psycopg_connect(monkeypatch)

    database.get_database_connection()

    connect_mock.assert_called_once_with(
        host='secret-host',
        database='db',
        user='user',
        password='pass',
        port=5432,
        connect_timeout=5,
    )
    assert connection.autocommit is False


def test_get_database_connection_falls_back_to_proxy_endpoint(monkeypatch):
    """If no cluster or secret host is present the proxy endpoint should be used."""
    _clear_connection_env(monkeypatch)
    monkeypatch.setenv('DB_SECRET_ARN', 'arn:secret')
    monkeypatch.setenv('DB_PROXY_ENDPOINT', 'proxy.example.com')

    secret = {'username': 'user', 'password': 'pass', 'dbname': 'db', 'port': 5432}
    _mock_secret_client(monkeypatch, secret)
    connect_mock, connection = _mock_psycopg_connect(monkeypatch)

    database.get_database_connection()

    connect_mock.assert_called_once_with(
        host='proxy.example.com',
        database='db',
        user='user',
        password='pass',
        port=5432,
        connect_timeout=5,
    )
    assert connection.autocommit is False