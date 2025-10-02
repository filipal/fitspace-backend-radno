"""
Database connection utilities
"""
import json
import boto3
import psycopg2
import os
import logging

logger = logging.getLogger(__name__)


def get_database_connection(timeout=5):
    """
    Get database connection via RDS Proxy using environment variables or AWS Secrets Manager fallback
    Uses shorter timeout and better error handling to prevent hangs
    """
    endpoint_context = 'unknown endpoint'

    try:
        # Try to use environment variables first (preferred method)
        if all(key in os.environ for key in ['DB_HOST', 'DB_NAME', 'DB_USERNAME', 'DB_PASSWORD']):
            logger.info("Using environment variables for database connection")
            db_host = os.environ['DB_HOST']
            db_name = os.environ['DB_NAME']
            db_username = os.environ['DB_USERNAME']
            db_password = os.environ['DB_PASSWORD']
            db_port = int(os.environ.get('DB_PORT', 5432))
            
            endpoint_context = f"DB_HOST environment variable ({db_host})"
            logger.info(f"Connecting to database via environment host: {db_host}")
            connection = psycopg2.connect(
                host=db_host,
                database=db_name,
                user=db_username,
                password=db_password,
                port=db_port,
                connect_timeout=timeout
                # Note: RDS Proxy doesn't support command-line options like statement_timeout
            )
            
        # Fallback to Secrets Manager if environment variables are not available
        else:
            logger.info("Environment variables not found, falling back to Secrets Manager")
            db_secret_arn = os.environ['DB_SECRET_ARN']
            
            # Get database credentials from Secrets Manager with timeout
            secrets_client = boto3.client('secretsmanager', config=boto3.session.Config(
                connect_timeout=3,
                read_timeout=3,
                retries={'max_attempts': 2}
            ))
            
            logger.info("Fetching database credentials from Secrets Manager")
            secret_response = secrets_client.get_secret_value(SecretId=db_secret_arn)
            secret = json.loads(secret_response['SecretString'])
            
            # Determine which endpoint to use for the connection
            if os.environ.get('DB_CLUSTER_ENDPOINT'):
                endpoint = os.environ['DB_CLUSTER_ENDPOINT']
                endpoint_context = f"DB_CLUSTER_ENDPOINT environment variable ({endpoint})"
            elif secret.get('host'):
                endpoint = secret['host']
                endpoint_context = f"secret host value ({endpoint})"
            else:
                endpoint = os.environ['DB_PROXY_ENDPOINT']
                endpoint_context = f"DB_PROXY_ENDPOINT environment variable ({endpoint})"

            logger.info(f"Connecting to database using {endpoint_context}")
            connection = psycopg2.connect(
                host=endpoint,
                database=secret.get('dbname', secret.get('engine', 'fitspace')),
                user=secret['username'],
                password=secret['password'],
                port=secret.get('port', 5432),
                connect_timeout=timeout
                # Note: RDS Proxy doesn't support command-line options like statement_timeout
            )
        
        # Set additional connection parameters for faster failure
        connection.autocommit = False
        
        logger.info("Database connection established successfully")
        return connection
        
    except KeyError as e:
        missing_env_vars = []
        # Check which environment variables are missing
        if not all(key in os.environ for key in ['DB_HOST', 'DB_NAME', 'DB_USERNAME', 'DB_PASSWORD']):
            missing_env_vars.extend(['DB_HOST', 'DB_NAME', 'DB_USERNAME', 'DB_PASSWORD'])
        if 'DB_SECRET_ARN' not in os.environ:
            missing_env_vars.append('DB_SECRET_ARN')
        secret_host_available = 'secret' in locals() and isinstance(secret, dict) and secret.get('host')
        if not secret_host_available and not any(key in os.environ for key in ['DB_CLUSTER_ENDPOINT', 'DB_PROXY_ENDPOINT']):
            missing_env_vars.extend(['DB_CLUSTER_ENDPOINT', 'DB_PROXY_ENDPOINT'])
        
        logger.error(f"Missing environment variables for database connection: {missing_env_vars}")
        raise Exception(f"Missing required environment variables. Need either [DB_HOST, DB_NAME, DB_USERNAME, DB_PASSWORD] or [DB_SECRET_ARN plus DB_CLUSTER_ENDPOINT/DB_PROXY_ENDPOINT]: {str(e)}")
    
    except psycopg2.OperationalError as e:
        error_message = f"Database connection failed (timeout or connectivity issue) while using {endpoint_context}: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)
    
    except psycopg2.Error as e:
        error_message = f"Database connection failed while using {endpoint_context}: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)
    
    except Exception as e:
        logger.error(f"Unexpected error getting database connection: {str(e)}")
        logger.error(f"Unexpected error getting database connection while using {endpoint_context}: {str(e)}")
        raise


def get_database_connection_with_retry(max_retries=2, timeout=5):
    """
    Get database connection with retry logic for better reliability
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Database connection attempt {attempt + 1}/{max_retries + 1}")
            return get_database_connection(timeout)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"Database connection attempt {attempt + 1} failed, retrying: {str(e)}")
                continue
            else:
                logger.error(f"All database connection attempts failed")
                raise last_exception


def execute_query(connection, query, params=None, fetch=True, timeout=10):
    """
    Execute a database query with error handling and timeout
    """
    cursor = None
    try:
        cursor = connection.cursor()
        
        # Set query timeout using SQL command instead of connection options
        # This works with RDS Proxy
        try:
            cursor.execute(f"SET statement_timeout = '{timeout}s'")
        except psycopg2.Error:
            # If setting timeout fails, continue without it
            logger.warning("Could not set statement timeout - continuing without query timeout")
        
        cursor.execute(query, params)

        if fetch:
            query_text = " ".join(query) if isinstance(query, (list, tuple)) else str(query)
            query_upper = query_text.strip().upper()
            has_returning = "RETURNING" in query_upper
            has_result_set = cursor.description is not None

            if has_result_set or has_returning:
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                if columns:
                    return [dict(zip(columns, row)) for row in rows]
                # Fallback: return rows without column mapping if description missing
                return [dict(enumerate(row)) for row in rows]

            # For statements without a result set, return affected row count
            return cursor.rowcount
        else:
            connection.commit()
            return cursor.rowcount
            
    except psycopg2.extensions.QueryCanceledError as e:
        connection.rollback()
        logger.error(f"Database query timeout after {timeout}s: {str(e)}")
        raise Exception(f"Database query timeout: {str(e)}")
        
    except psycopg2.Error as e:
        connection.rollback()
        logger.error(f"Database query error: {str(e)}")
        raise Exception(f"Database query failed: {str(e)}")
    
    finally:
        if cursor:
            cursor.close()
