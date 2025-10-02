"""Avatar data model and database operations."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from src.utils.database import execute_query

logger = logging.getLogger(__name__)


class Avatar:
    """Model class encapsulating avatar persistence logic."""

    REQUIRED_FIELDS = ("user_id", "display_name")
    NUMERIC_FIELDS: Iterable[str] = (
        "height_cm",
        "weight_kg",
        "body_fat_percent",
        "shoulder_circumference_cm",
        "waist_cm",
        "hips_cm",
    )
    def __init__(self, connection):
        self.connection = connection

    def list_by_user(
        self, user_id: int, limit: Optional[int] = None, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Return a paginated list of avatars for a specific user."""
        logger.debug(
            "Listing avatars for user %s with limit=%s offset=%s",
            user_id,
            limit,
            offset,
        )
        try:
            query = [
                "SELECT *",
                "FROM avatars",
                "WHERE user_id = %s",
                "ORDER BY created_at DESC, id DESC",
            ]
            params: List[Any] = [user_id]

            if limit is not None:
                query.append("LIMIT %s OFFSET %s")
                params.extend([limit, offset])
            elif offset:
                query.append("OFFSET %s")
                params.append(offset)

            rows = execute_query(self.connection, "\n".join(query), tuple(params))
            self.connection.commit()
            return [self._serialize(row) for row in rows]
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error(
                "Failed to list avatars for user_id=%s: %s", user_id, exc, exc_info=True
            )
            raise

    def get(self, avatar_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single avatar by its identifier."""
        logger.debug("Fetching avatar %s", avatar_id)
        try:
            rows = execute_query(
                self.connection,
                "SELECT * FROM avatars WHERE id = %s",
                (avatar_id,),
            )
            self.connection.commit()
            if not rows:
                logger.info("Avatar %s not found", avatar_id)
                return None
            return self._serialize(rows[0])
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error("Failed to fetch avatar_id=%s: %s", avatar_id, exc, exc_info=True)
            raise

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new avatar record after validating required fields."""
        logger.debug("Creating avatar with data: %s", kwargs)
        missing = [field for field in self.REQUIRED_FIELDS if not kwargs.get(field)]
        if missing:
            raise ValueError(f"Missing required avatar fields: {', '.join(missing)}")

        columns = list(kwargs.keys())
        values_placeholders = ["%s"] * len(columns)
        params = [kwargs[column] for column in columns]

        query = (
            f"INSERT INTO avatars ({', '.join(columns)}) "
            f"VALUES ({', '.join(values_placeholders)}) RETURNING *"
        )

        try:
            rows = execute_query(self.connection, query, tuple(params))
            self.connection.commit()
            avatar = self._serialize(rows[0])
            logger.info("Created avatar %s for user %s", avatar["id"], avatar["user_id"])
            return avatar
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error("Failed to create avatar: %s", exc, exc_info=True)
            raise

    def update_partial(self, avatar_id: int, **fields: Any) -> Optional[Dict[str, Any]]:
        """Update provided fields for the avatar, refreshing the updated timestamp."""
        if not fields:
            raise ValueError("No fields provided for avatar update")

        logger.debug("Updating avatar %s with fields: %s", avatar_id, fields)

        set_clauses = [f"{column} = %s" for column in fields]
        params = list(fields.values())
        set_clauses.append("updated_at = NOW()")
        params.append(avatar_id)

        query = (
            f"UPDATE avatars SET {', '.join(set_clauses)} WHERE id = %s RETURNING *"
        )

        try:

            rows = execute_query(self.connection, query, tuple(params))
            self.connection.commit()
            if not rows:
                logger.info("Avatar %s not found for update", avatar_id)
                return None
            avatar = self._serialize(rows[0])
            logger.info("Updated avatar %s", avatar_id)
            return avatar
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error("Failed to update avatar_id=%s: %s", avatar_id, exc, exc_info=True)
            raise

    def delete(self, avatar_id: int) -> bool:
        """Delete an avatar and return True if a record was removed."""
        logger.debug("Deleting avatar %s", avatar_id)
        try:
            rows = execute_query(
                self.connection,
                "DELETE FROM avatars WHERE id = %s RETURNING id",
                (avatar_id,),
            )
            self.connection.commit()
            deleted = bool(rows)
            if deleted:
                logger.info("Deleted avatar %s", avatar_id)
            else:
                logger.info("No avatar deleted for id %s", avatar_id)
            return deleted
        except Exception as exc:  # pragma: no cover - passthrough
            self.connection.rollback()
            logger.error("Failed to delete avatar_id=%s: %s", avatar_id, exc, exc_info=True)
            raise

    def _serialize(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert decimal values into JSON serialisable primitives."""
        serialized = dict(row)
        for field in self.NUMERIC_FIELDS:
            value = serialized.get(field)
            if isinstance(value, Decimal):
                serialized[field] = float(value)
        return serialized