"""
HTTP response utilities for Lambda functions
"""
import json
import logging

logger = logging.getLogger(__name__)


def create_response(status_code, body, headers=None):
    """
    Create a standardized API Gateway response
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,PATCH'
    }
    
    if headers:
        default_headers.update(headers)
    
    response = {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    }
    
    logger.info(f"Response created with status {status_code}")
    return response


def create_error_response(status_code, error_message, details=None):
    """
    Create a standardized error response
    """
    error_body = {
        'error': error_message,
        'statusCode': status_code
    }
    
    if details:
        error_body['details'] = details
    
    logger.error(f"Error response: {error_message} - {details}")
    return create_response(status_code, error_body)


def create_success_response(data, message=None):
    """
    Create a standardized success response
    """
    response_body = {
        'success': True,
        'data': data
    }
    
    if message:
        response_body['message'] = message
    
    return create_response(200, response_body)


def create_paginated_response(data, page, limit, total_count, message=None):
    """
    Create a paginated response
    """
    response_body = {
        'success': True,
        'data': data,
        'pagination': {
            'page': page,
            'limit': limit,
            'total_count': total_count,
            'total_pages': (total_count + limit - 1) // limit,
            'has_next': page * limit < total_count,
            'has_previous': page > 1
        }
    }
    
    if message:
        response_body['message'] = message
    
    return create_response(200, response_body)
