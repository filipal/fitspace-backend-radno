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
    try:
        # Try to use environment variables first (preferred method)
        if all(key in os.environ for key in ['DB_HOST', 'DB_NAME', 'DB_USERNAME', 'DB_PASSWORD']):
            logger.info("Using environment variables for database connection")
            db_host = os.environ['DB_HOST']
            db_name = os.environ['DB_NAME']
            db_username = os.environ['DB_USERNAME']
            db_password = os.environ['DB_PASSWORD']
            db_port = int(os.environ.get('DB_PORT', 5432))
            
            logger.info(f"Connecting to database via RDS Proxy: {db_host}")
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
            db_proxy_endpoint = os.environ['DB_PROXY_ENDPOINT']
            
            # Get database credentials from Secrets Manager with timeout
            secrets_client = boto3.client('secretsmanager', config=boto3.session.Config(
                connect_timeout=3,
                read_timeout=3,
                retries={'max_attempts': 2}
            ))
            
            logger.info("Fetching database credentials from Secrets Manager")
            secret_response = secrets_client.get_secret_value(SecretId=db_secret_arn)
            secret = json.loads(secret_response['SecretString'])
            
            # Connect to database via RDS Proxy with aggressive timeouts
            logger.info(f"Connecting to database via RDS Proxy: {db_proxy_endpoint}")
            connection = psycopg2.connect(
                host=db_proxy_endpoint,
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
        if 'DB_SECRET_ARN' not in os.environ and 'DB_PROXY_ENDPOINT' not in os.environ:
            missing_env_vars.extend(['DB_SECRET_ARN', 'DB_PROXY_ENDPOINT'])
        
        logger.error(f"Missing environment variables for database connection: {missing_env_vars}")
        raise Exception(f"Missing required environment variables. Need either [DB_HOST, DB_NAME, DB_USERNAME, DB_PASSWORD] or [DB_SECRET_ARN, DB_PROXY_ENDPOINT]: {str(e)}")
    
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection timeout/operational error: {str(e)}")
        raise Exception(f"Database connection failed (timeout or connectivity issue): {str(e)}")
    
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {str(e)}")
        raise Exception(f"Database connection failed: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error getting database connection: {str(e)}")
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
            if query.strip().upper().startswith('SELECT'):
                # For SELECT queries, fetch results
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result = [dict(zip(columns, row)) for row in rows]
                return result
            else:
                # For non-SELECT queries, return affected row count
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
