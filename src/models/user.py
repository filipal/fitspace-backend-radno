"""
User data models and database operations
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.utils.database import execute_query

logger = logging.getLogger(__name__)


class User:
    """User model for database operations"""
    
    def __init__(self, connection):
        self.connection = connection
    
    def get_all(self, limit: int = 10, offset: int = 0, search: str = None) -> List[Dict[str, Any]]:
        """
        Get all users with optional pagination and search
        """
        try:
            base_query = """
                SELECT id, name, email, created_at, updated_at 
                FROM users 
            """
            params = []
            
            if search:
                base_query += "WHERE name ILIKE %s OR email ILIKE %s "
                params.extend([f"%{search}%", f"%{search}%"])
            
            base_query += "ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            users = execute_query(self.connection, base_query, params)
            logger.info(f"Retrieved {len(users)} users")
            return users
            
        except Exception as e:
            logger.error(f"Error getting users: {str(e)}")
            raise
    
    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID
        """
        try:
            result = execute_query(
                self.connection,
                "SELECT id, name, email, created_at, updated_at FROM users WHERE id = %s",
                (user_id,)
            )
            
            if result:
                logger.info(f"Retrieved user with ID: {user_id}")
                return result[0]
            
            logger.warning(f"User not found with ID: {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            raise
    
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email
        """
        try:
            result = execute_query(
                self.connection,
                "SELECT id, name, email, created_at, updated_at FROM users WHERE email = %s",
                (email,)
            )
            
            if result:
                logger.info(f"Retrieved user with email: {email}")
                return result[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            raise
    
    def create(self, name: str, email: str, **kwargs) -> Dict[str, Any]:
        """
        Create a new user
        """
        try:
            # Check if user already exists
            existing = self.get_by_email(email)
            if existing:
                raise ValueError(f"User with email {email} already exists")
            
            # Additional fields if provided
            phone = kwargs.get('phone')
            bio = kwargs.get('bio')
            
            query = """
                INSERT INTO users (name, email, phone, bio, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, NOW(), NOW()) 
                RETURNING id, name, email, phone, bio, created_at, updated_at
            """
            
            result = execute_query(
                self.connection,
                query,
                (name, email, phone, bio)
            )
            
            self.connection.commit()
            logger.info(f"Created user: {email}")
            return result[0]
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    def update(self, user_id: int, **updates) -> Optional[Dict[str, Any]]:
        """
        Update a user by ID
        """
        try:
            # Check if user exists
            existing = self.get_by_id(user_id)
            if not existing:
                return None
            
            # Build dynamic update query
            update_fields = []
            params = []
            
            allowed_fields = ['name', 'email', 'phone', 'bio']
            for field in allowed_fields:
                if field in updates:
                    update_fields.append(f"{field} = %s")
                    params.append(updates[field])
            
            if not update_fields:
                raise ValueError("No valid fields to update")
            
            # Add updated_at timestamp
            update_fields.append("updated_at = NOW()")
            params.append(user_id)
            
            query = f"""
                UPDATE users 
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, name, email, phone, bio, created_at, updated_at
            """
            
            result = execute_query(self.connection, query, params)
            self.connection.commit()
            
            logger.info(f"Updated user ID: {user_id}")
            return result[0]
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise
    
    def delete(self, user_id: int) -> bool:
        """
        Delete a user by ID (soft delete - you might want to add a deleted_at field)
        """
        try:
            # Check if user exists
            existing = self.get_by_id(user_id)
            if not existing:
                return False
            
            result = execute_query(
                self.connection,
                "DELETE FROM users WHERE id = %s",
                (user_id,),
                fetch=False
            )
            
            self.connection.commit()
            logger.info(f"Deleted user ID: {user_id}")
            return result > 0
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise
    
    def count(self, search: str = None) -> int:
        """
        Get total count of users (for pagination)
        """
        try:
            base_query = "SELECT COUNT(*) as total FROM users"
            params = []
            
            if search:
                base_query += " WHERE name ILIKE %s OR email ILIKE %s"
                params.extend([f"%{search}%", f"%{search}%"])
            
            result = execute_query(self.connection, base_query, params)
            return result[0]['total'] if result else 0
            
        except Exception as e:
            logger.error(f"Error counting users: {str(e)}")
            raise
