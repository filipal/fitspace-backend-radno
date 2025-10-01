"""Avatar data model and database operations"""
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from src.utils.database import execute_query


logger = logging.getLogger(__name__)


class Avatar:
    """Model class encapsulating avatar persistence logic."""

    _RETURNING_COLUMNS = (
        "id, user_id, display_name, age, gender, height_cm, weight_kg, "
        "body_fat_percent, shoulder_circumference_cm, waist_cm, hips_cm, "
        "notes, created_at, updated_at"
    )

    _NUMERIC_FIELDS = {
        "height_cm",
        "weight_kg",
        "body_fat_percent",
        "shoulder_circumference_cm",
        "waist_cm",
        "hips_cm",
    }

    def __init__(self, connection):
        self.connection = connection

    def list_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all avatars for the provided user ordered by creation time."""
        try:
            query = f"""
                SELECT {self._RETURNING_COLUMNS}
                FROM avatars
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
            """
            rows = execute_query(self.connection, query, (user_id,))
            return [self._serialize_avatar(row) for row in rows]
        except Exception as exc:  # pragma: no cover - passthrough
            logger.error("Error listing avatars for user %s: %s", user_id, exc)
            raise

    def get(self, user_id: int, avatar_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single avatar for a user."""
        try:
            query = f"""
                SELECT {self._RETURNING_COLUMNS}
                FROM avatars
                WHERE user_id = %s AND id = %s
            """
            rows = execute_query(self.connection, query, (user_id, avatar_id))
            if not rows:
                return None
            return self._serialize_avatar(rows[0])
        except Exception as exc:  # pragma: no cover - passthrough
            logger.error(
                "Error retrieving avatar %s for user %s: %s", avatar_id, user_id, exc
            )
            raise

    def create(self, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new avatar for the given user."""
        try:
            query = f"""
                INSERT INTO avatars (
                    user_id,
                    display_name,
                    age,
                    gender,
                    height_cm,
                    weight_kg,
                    body_fat_percent,
                    shoulder_circumference_cm,
                    waist_cm,
                    hips_cm,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {self._RETURNING_COLUMNS}
            """

            params = (
                user_id,
                payload.get("display_name"),
                payload.get("age"),
                payload.get("gender"),
                payload.get("height_cm"),
                payload.get("weight_kg"),
                payload.get("body_fat_percent"),
                payload.get("shoulder_circumference_cm"),
                payload.get("waist_cm"),
                payload.get("hips_cm"),
                payload.get("notes"),
            )

            rows = execute_query(self.connection, query, params)
            self.connection.commit()
            return self._serialize_avatar(rows[0])
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error("Error creating avatar for user %s: %s", user_id, exc)
            raise

    def update(
        self, user_id: int, avatar_id: int, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing avatar for the user."""
        if not updates:
            raise ValueError("No updates provided")

        try:
            set_clauses = []
            params: List[Any] = []

            for key, value in updates.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)

            params.extend([user_id, avatar_id])

            query = f"""
                UPDATE avatars
                SET {', '.join(set_clauses)}
                WHERE user_id = %s AND id = %s
                RETURNING {self._RETURNING_COLUMNS}
            """

            rows = execute_query(self.connection, query, tuple(params))
            self.connection.commit()

            if not rows:
                return None

            return self._serialize_avatar(rows[0])
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error(
                "Error updating avatar %s for user %s: %s", avatar_id, user_id, exc
            )
            raise

    def delete(self, user_id: int, avatar_id: int) -> bool:
        """Delete an avatar for the user."""
        try:
            query = "DELETE FROM avatars WHERE user_id = %s AND id = %s"
            deleted = execute_query(
                self.connection, query, (user_id, avatar_id), fetch=False
            )
            return deleted > 0
        except Exception as exc:  # pragma: no cover - passthrough
            logger.error(
                "Error deleting avatar %s for user %s: %s", avatar_id, user_id, exc
            )
            raise

    def _serialize_avatar(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce database types into JSON serialisable primitives."""
        serialized = dict(row)
        for field in self._NUMERIC_FIELDS:
            value = serialized.get(field)
            if isinstance(value, Decimal):
                serialized[field] = float(value)
        return serialized