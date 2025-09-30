"""
API route handlers for the backend
"""
import json
import logging
import os
from src.utils.response import create_response, create_error_response, create_success_response, create_paginated_response
from src.utils.database import execute_query
from src.models.user import User

logger = logging.getLogger(__name__)


def handle_request(event, connection):
    """
    Main request router with lazy database connection handling
    """
    try:
        path = event.get('path', '')
        method = event.get('httpMethod', 'GET')
        
        logger.info(f"Routing request: {method} {path}")
        
        # Handle CORS preflight requests
        if method == 'OPTIONS':
            return create_response(200, {'message': 'CORS preflight'})
        
        # Health check endpoint - basic version without DB
        if path == '/status' and method == 'GET':
            return handle_status_basic()
            
        # Health check endpoint with database test
        if path == '/status/db' and method == 'GET':
            if not connection:
                # Need to establish connection for database test
                from src.utils.database import get_database_connection_with_retry
                try:
                    connection = get_database_connection_with_retry(max_retries=1, timeout=3)
                    result = handle_status_with_db(connection)
                    connection.close()
                    return result
                except Exception as e:
                    logger.error(f"Failed to establish DB connection for health check: {str(e)}")
                    return create_error_response(503, 'Database connection failed', str(e))
            else:
                return handle_status_with_db(connection)
        
        # API v1 routes - these require database connection
        if path.startswith('/api/v1'):
            if not connection:
                return create_error_response(503, 'Database connection required but not available')
            return handle_v1_routes(event, connection)
        
        # Default 404 response
        return create_error_response(404, 'Endpoint not found')
        
    except Exception as e:
        logger.error(f"Error in handle_request: {str(e)}")
        return create_error_response(500, 'Internal server error', str(e))


def handle_status_basic():
    """
    Basic health check endpoint without database dependency
    This endpoint should always respond quickly and not hang
    """
    import time
    try:
        return create_success_response({
            'status': 'healthy',
            'service': 'fitspace-backend',
            'timestamp': int(time.time()),
            'version': '1.0.0',
            'environment': os.environ.get('ENVIRONMENT', 'unknown'),
            'database': 'not_tested'
        })
    except Exception as e:
        logger.error(f"Basic health check failed: {str(e)}")
        return create_error_response(500, 'Basic health check failed', str(e))


def handle_status_with_db(connection):
    """
    Health check endpoint with database connectivity test
    This is the more comprehensive health check
    """
    import time
    try:
        # Test database connection with timeout
        start_time = time.time()
        result = execute_query(connection, "SELECT 1 as health_check", timeout=5)
        db_response_time = round((time.time() - start_time) * 1000, 2)  # milliseconds
        
        return create_success_response({
            'status': 'healthy',
            'service': 'fitspace-backend', 
            'timestamp': int(time.time()),
            'version': '1.0.0',
            'environment': os.environ.get('ENVIRONMENT', 'unknown'),
            'database': {
                'status': 'connected',
                'response_time_ms': db_response_time,
                'test_result': result[0]['health_check'] if result else None
            }
        })
        
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return create_error_response(503, 'Database health check failed', str(e))


def handle_status(connection):
    """
    Legacy health check endpoint - kept for backward compatibility
    Now uses the database version but with error fallback
    """
    try:
        return handle_status_with_db(connection)
    except Exception as e:
        # Fallback to basic status if database check fails
        logger.warning(f"Database health check failed, falling back to basic: {str(e)}")
        return handle_status_basic()


def handle_v1_routes(event, connection):
    """
    Handle API v1 routes
    """
    path = event.get('path', '')
    method = event.get('httpMethod', 'GET')
    
    # Handle CORS preflight requests for API routes
    if method == 'OPTIONS':
        return create_response(200, {'message': 'CORS preflight'})
    
    # Remove /api/v1 prefix
    route = path.replace('/api/v1', '') or '/'
    
    # User endpoints
    if route == '/users' and method == 'GET':
        return get_users(event, connection)
    elif route == '/users' and method == 'POST':
        return create_user(event, connection)
    elif route.startswith('/users/') and method == 'GET':
        user_id = route.split('/')[-1]
        return get_user(user_id, connection)
    elif route.startswith('/users/') and method == 'PUT':
        user_id = route.split('/')[-1]
        return update_user(user_id, event, connection)
    elif route.startswith('/users/') and method == 'DELETE':
        user_id = route.split('/')[-1]
        return delete_user(user_id, connection)
    elif route == '/users/search' and method == 'GET':
        return search_users(event, connection)
    
    return create_error_response(404, f'Route not found: {method} {route}')


def get_users(event, connection):
    """
    Get all users with pagination and optional search
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        limit = min(int(query_params.get('limit', 10)), 100)  # Max 100 items
        offset = int(query_params.get('offset', 0))
        search = query_params.get('search')
        
        # Use User model
        user_model = User(connection)
        users = user_model.get_all(limit=limit, offset=offset, search=search)
        total_count = user_model.count(search=search)
        
        # Calculate pagination info
        page = (offset // limit) + 1
        
        return create_paginated_response(
            data=users,
            page=page,
            limit=limit,
            total_count=total_count,
            message=f'Retrieved {len(users)} users'
        )
        
    except ValueError as e:
        logger.error(f"Validation error in get_users: {str(e)}")
        return create_error_response(400, 'Invalid query parameters', str(e))
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        return create_error_response(500, 'Failed to retrieve users', str(e))


def create_user(event, connection):
    """
    Create a new user
    """
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        name = body.get('name', '').strip()
        email = body.get('email', '').strip().lower()
        
        if not name or not email:
            return create_error_response(400, 'Name and email are required')
        
        if len(name) < 2 or len(name) > 100:
            return create_error_response(400, 'Name must be between 2 and 100 characters')
        
        # Basic email validation
        if '@' not in email or '.' not in email.split('@')[-1]:
            return create_error_response(400, 'Invalid email format')
        
        # Optional fields
        phone = body.get('phone', '').strip()
        bio = body.get('bio', '').strip()
        
        # Validate optional fields
        if phone and len(phone) > 20:
            return create_error_response(400, 'Phone number too long')
        
        if bio and len(bio) > 500:
            return create_error_response(400, 'Bio must be less than 500 characters')
        
        # Create user using User model
        user_model = User(connection)
        new_user = user_model.create(
            name=name,
            email=email,
            phone=phone if phone else None,
            bio=bio if bio else None
        )
        
        return create_success_response(new_user, 'User created successfully')
        
    except json.JSONDecodeError:
        return create_error_response(400, 'Invalid JSON in request body')
    except ValueError as e:
        logger.error(f"Validation error in create_user: {str(e)}")
        return create_error_response(400, str(e))
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return create_error_response(500, 'Failed to create user', str(e))


def get_user(user_id, connection):
    """
    Get a specific user by ID
    """
    try:
        # Validate user_id
        try:
            user_id_int = int(user_id)
            if user_id_int <= 0:
                raise ValueError("Invalid user ID")
        except ValueError:
            return create_error_response(400, 'Invalid user ID format')
        
        # Get user using User model
        user_model = User(connection)
        user = user_model.get_by_id(user_id_int)
        
        if not user:
            return create_error_response(404, 'User not found')
        
        return create_success_response(user, 'User retrieved successfully')
        
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        return create_error_response(500, 'Failed to retrieve user', str(e))


def update_user(user_id, event, connection):
    """
    Update a specific user by ID
    """
    try:
        # Validate user_id
        try:
            user_id_int = int(user_id)
            if user_id_int <= 0:
                raise ValueError("Invalid user ID")
        except ValueError:
            return create_error_response(400, 'Invalid user ID format')
        
        body = json.loads(event.get('body', '{}'))
        
        # Prepare updates
        updates = {}
        
        # Validate and prepare name
        if 'name' in body:
            name = body['name'].strip()
            if not name:
                return create_error_response(400, 'Name cannot be empty')
            if len(name) < 2 or len(name) > 100:
                return create_error_response(400, 'Name must be between 2 and 100 characters')
            updates['name'] = name
        
        # Validate and prepare email
        if 'email' in body:
            email = body['email'].strip().lower()
            if not email:
                return create_error_response(400, 'Email cannot be empty')
            if '@' not in email or '.' not in email.split('@')[-1]:
                return create_error_response(400, 'Invalid email format')
            updates['email'] = email
        
        # Validate and prepare phone
        if 'phone' in body:
            phone = body['phone'].strip() if body['phone'] else None
            if phone and len(phone) > 20:
                return create_error_response(400, 'Phone number too long')
            updates['phone'] = phone
        
        # Validate and prepare bio
        if 'bio' in body:
            bio = body['bio'].strip() if body['bio'] else None
            if bio and len(bio) > 500:
                return create_error_response(400, 'Bio must be less than 500 characters')
            updates['bio'] = bio
        
        if not updates:
            return create_error_response(400, 'No valid fields to update')
        
        # Update user using User model
        user_model = User(connection)
        updated_user = user_model.update(user_id_int, **updates)
        
        if not updated_user:
            return create_error_response(404, 'User not found')
        
        return create_success_response(updated_user, 'User updated successfully')
        
    except json.JSONDecodeError:
        return create_error_response(400, 'Invalid JSON in request body')
    except ValueError as e:
        logger.error(f"Validation error in update_user: {str(e)}")
        return create_error_response(400, str(e))
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        return create_error_response(500, 'Failed to update user', str(e))


def delete_user(user_id, connection):
    """
    Delete a specific user by ID
    """
    try:
        # Validate user_id
        try:
            user_id_int = int(user_id)
            if user_id_int <= 0:
                raise ValueError("Invalid user ID")
        except ValueError:
            return create_error_response(400, 'Invalid user ID format')
        
        # Delete user using User model
        user_model = User(connection)
        deleted = user_model.delete(user_id_int)
        
        if not deleted:
            return create_error_response(404, 'User not found')
        
        return create_success_response(
            {'id': user_id_int}, 
            'User deleted successfully'
        )
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return create_error_response(500, 'Failed to delete user', str(e))


def search_users(event, connection):
    """
    Search users by name or email
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        search_term = query_params.get('q', '').strip()
        
        if not search_term:
            return create_error_response(400, 'Search term is required (use ?q=search_term)')
        
        if len(search_term) < 2:
            return create_error_response(400, 'Search term must be at least 2 characters')
        
        limit = min(int(query_params.get('limit', 20)), 100)
        offset = int(query_params.get('offset', 0))
        
        # Search users using User model
        user_model = User(connection)
        users = user_model.get_all(limit=limit, offset=offset, search=search_term)
        total_count = user_model.count(search=search_term)
        
        page = (offset // limit) + 1
        
        return create_paginated_response(
            data=users,
            page=page,
            limit=limit,
            total_count=total_count,
            message=f'Found {len(users)} users matching "{search_term}"'
        )
        
    except ValueError as e:
        logger.error(f"Validation error in search_users: {str(e)}")
        return create_error_response(400, 'Invalid query parameters', str(e))
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        return create_error_response(500, 'Failed to search users', str(e))
