import json
import boto3
import psycopg2
import os
import logging
from src.routes import api_routes
from src.utils.database import get_database_connection_with_retry
from src.utils.response import create_response, create_error_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Main Lambda handler for API Gateway requests
    Uses lazy database connection loading to prevent hangs
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    connection = None
    
    try:
        # Handle CORS preflight requests immediately without DB
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, {'message': 'CORS preflight'})
        
        # Check if this is a basic status check that doesn't need DB
        path = event.get('path', '')
        if path == '/status':
            # For basic status, don't establish DB connection
            # The route handler will decide if DB is needed
            response = api_routes.handle_request(event, None)
            return response
        
        # For all other routes, establish database connection with retry and timeout
        logger.info("Establishing database connection for API request")
        connection = get_database_connection_with_retry(max_retries=1, timeout=3)
        
        # Route the request
        response = api_routes.handle_request(event, connection)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_error_response(500, 'Internal server error', str(e))
    
    finally:
        # Close database connection if it exists
        if connection:
            try:
                connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}")
