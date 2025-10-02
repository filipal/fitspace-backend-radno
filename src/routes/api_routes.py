"""
API route handlers for the backend
"""
import json
import logging
import os
from src.utils.response import create_response, create_error_response, create_success_response, create_paginated_response
from src.utils.database import execute_query
from src.models.user import User
from src.models.avatar import Avatar

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

    segments = [segment for segment in route.split('/') if segment]

    # User endpoints
    if route == '/users' and method == 'GET':
        return get_users(event, connection)
    elif route == '/users' and method == 'POST':
        return create_user(event, connection)
    elif route == '/users/search' and method == 'GET':
        return search_users(event, connection)

    elif len(segments) >= 2 and segments[0] == 'users' and segments[1] == 'search':
        return create_error_response(404, f'Route not found: {method} {route}')
    elif len(segments) >= 3 and segments[0] == 'users' and segments[2] == 'avatars':
        user_id = segments[1]
        avatar_segments = segments[3:]

        if not avatar_segments:
            if method == 'POST':
                return create_avatar(user_id, event, connection)
            if method == 'GET':
                return list_avatars(user_id, connection)
        elif len(avatar_segments) == 1:
            avatar_id = avatar_segments[0]
            if method == 'GET':
                return get_avatar(user_id, avatar_id, connection)
            if method == 'PATCH':
                return update_avatar(user_id, avatar_id, event, connection)
            if method == 'DELETE':
                return delete_avatar(user_id, avatar_id, connection)

        return create_error_response(404, f'Route not found: {method} {route}')
    elif len(segments) >= 2 and segments[0] == 'users':
        user_id = segments[1]
        if method == 'GET':
            return get_user(user_id, connection)
        if method == 'PUT':
            return update_user(user_id, event, connection)
        if method == 'DELETE':
            return delete_user(user_id, connection)
    elif route == '/users/search' and method == 'GET':
        return search_users(event, connection)

    return create_error_response(404, f'Route not found: {method} {route}')

def _parse_positive_int(value, error_message):
    try:
        parsed = int(value)
        if parsed <= 0:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise ValueError(error_message)


def _validate_avatar_payload(payload, *, partial=False):
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object')

    allowed_fields = {
        'display_name',
        'age',
        'gender',
        'height_cm',
        'weight_kg',
        'body_fat_percent',
        'shoulder_circumference_cm',
        'waist_cm',
        'hips_cm',
        'notes'
    }

    unknown_fields = set(payload.keys()) - allowed_fields
    if unknown_fields:
        raise ValueError(f'Unsupported avatar fields: {", ".join(sorted(unknown_fields))}')

    cleaned = {}

    if 'display_name' in payload:
        display_name = str(payload['display_name']).strip()
        if display_name and len(display_name) > 255:
            raise ValueError('Display name must be 255 characters or less')
        cleaned['display_name'] = display_name or None

    if 'age' in payload:
        age_raw = payload['age']
        if age_raw is None or str(age_raw).strip() == '':
            cleaned['age'] = None
        else:
            try:
                age_value = int(age_raw)
            except (TypeError, ValueError):
                raise ValueError('Age must be an integer')
            if age_value < 0 or age_value > 120:
                raise ValueError('Age must be between 0 and 120')
            cleaned['age'] = age_value

    if 'gender' in payload:
        gender = str(payload['gender']).strip().lower()
        if gender:
            allowed_genders = {
                'male',
                'female',
                'non-binary',
                'other',
                'prefer_not_to_say'
            }
            if gender not in allowed_genders:
                raise ValueError('Gender must be one of: male, female, non-binary, other, prefer_not_to_say')
            cleaned['gender'] = gender
        else:
            cleaned['gender'] = None

    numeric_constraints = {
        'height_cm': (50, 300),
        'weight_kg': (20, 500),
        'body_fat_percent': (0, 80),
        'shoulder_circumference_cm': (20, 300),
        'waist_cm': (30, 300),
        'hips_cm': (30, 300)
    }

    for field, (minimum, maximum) in numeric_constraints.items():
        if field in payload:
            raw_value = payload[field]
            if raw_value is None or str(raw_value).strip() == '':
                cleaned[field] = None
                continue
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError):
                raise ValueError(f'{field} must be a number')
            if numeric_value < minimum or numeric_value > maximum:
                raise ValueError(f'{field} must be between {minimum} and {maximum}')
            cleaned[field] = numeric_value

    if 'notes' in payload:
        notes_value = str(payload['notes']).strip()
        if notes_value and len(notes_value) > 1000:
            raise ValueError('Notes must be 1000 characters or less')
        cleaned['notes'] = notes_value or None

    if not partial and not cleaned:
        raise ValueError('At least one avatar attribute must be provided')

    if partial and not cleaned:
        raise ValueError('No valid avatar fields provided for update')

    return cleaned


def create_avatar(user_id, event, connection):
    try:
        user_id_int = _parse_positive_int(user_id, 'Invalid user ID format')
        body = json.loads(event.get('body', '{}'))
        payload = _validate_avatar_payload(body, partial=False)

        avatar_model = Avatar(connection)
        created_avatar = avatar_model.create(user_id_int, payload)

        return create_success_response(created_avatar, 'Avatar created successfully')
    except json.JSONDecodeError:
        return create_error_response(400, 'Invalid JSON in request body')
    except ValueError as exc:
        logger.error(f'Validation error in create_avatar: {str(exc)}')
        return create_error_response(400, str(exc))
    except Exception as exc:
        logger.error(f'Error creating avatar for user {user_id}: {str(exc)}')
        return create_error_response(500, 'Failed to create avatar', str(exc))


def list_avatars(user_id, connection):
    try:
        user_id_int = _parse_positive_int(user_id, 'Invalid user ID format')
        avatar_model = Avatar(connection)
        avatars = avatar_model.list_for_user(user_id_int)
        return create_success_response(avatars, 'Avatars retrieved successfully')
    except ValueError as exc:
        logger.error(f'Validation error in list_avatars: {str(exc)}')
        return create_error_response(400, str(exc))
    except Exception as exc:
        logger.error(f'Error listing avatars for user {user_id}: {str(exc)}')
        return create_error_response(500, 'Failed to retrieve avatars', str(exc))


def get_avatar(user_id, avatar_id, connection):
    try:
        user_id_int = _parse_positive_int(user_id, 'Invalid user ID format')
        avatar_id_int = _parse_positive_int(avatar_id, 'Invalid avatar ID format')

        avatar_model = Avatar(connection)
        avatar = avatar_model.get(user_id_int, avatar_id_int)

        if not avatar:
            return create_error_response(404, 'Avatar not found')

        return create_success_response(avatar, 'Avatar retrieved successfully')
    except ValueError as exc:
        logger.error(f'Validation error in get_avatar: {str(exc)}')
        return create_error_response(400, str(exc))
    except Exception as exc:
        logger.error(f'Error retrieving avatar {avatar_id} for user {user_id}: {str(exc)}')
        return create_error_response(500, 'Failed to retrieve avatar', str(exc))


def update_avatar(user_id, avatar_id, event, connection):
    try:
        user_id_int = _parse_positive_int(user_id, 'Invalid user ID format')
        avatar_id_int = _parse_positive_int(avatar_id, 'Invalid avatar ID format')
        body = json.loads(event.get('body', '{}'))
        payload = _validate_avatar_payload(body, partial=True)

        avatar_model = Avatar(connection)
        updated_avatar = avatar_model.update(user_id_int, avatar_id_int, payload)

        if not updated_avatar:
            return create_error_response(404, 'Avatar not found')

        return create_success_response(updated_avatar, 'Avatar updated successfully')
    except json.JSONDecodeError:
        return create_error_response(400, 'Invalid JSON in request body')
    except ValueError as exc:
        logger.error(f'Validation error in update_avatar: {str(exc)}')
        return create_error_response(400, str(exc))
    except Exception as exc:
        logger.error(f'Error updating avatar {avatar_id} for user {user_id}: {str(exc)}')
        return create_error_response(500, 'Failed to update avatar', str(exc))


def delete_avatar(user_id, avatar_id, connection):
    try:
        user_id_int = _parse_positive_int(user_id, 'Invalid user ID format')
        avatar_id_int = _parse_positive_int(avatar_id, 'Invalid avatar ID format')

        avatar_model = Avatar(connection)
        deleted = avatar_model.delete(user_id_int, avatar_id_int)

        if not deleted:
            return create_error_response(404, 'Avatar not found')

        return create_success_response({'id': avatar_id_int}, 'Avatar deleted successfully')
    except ValueError as exc:
        logger.error(f'Validation error in delete_avatar: {str(exc)}')
        return create_error_response(400, str(exc))
    except Exception as exc:
        logger.error(f'Error deleting avatar {avatar_id} for user {user_id}: {str(exc)}')
        return create_error_response(500, 'Failed to delete avatar', str(exc))

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

        avatar_model = Avatar(connection)
        user['avatars'] = avatar_model.list_for_user(user_id_int)

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
