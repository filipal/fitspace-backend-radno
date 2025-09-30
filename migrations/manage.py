"""
Database migration management script
"""
import os
import sys
import json
import boto3
import psycopg2
import logging
from alembic.config import Config
from alembic import command

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

logger = logging.getLogger(__name__)


def get_database_connection():
    """
    Get database connection using environment variables or AWS Secrets Manager fallback
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
            
            connection = psycopg2.connect(
                host=db_host,
                database=db_name,
                user=db_username,
                password=db_password,
                port=db_port
            )
            
            # Return connection and secret-like dict for compatibility
            secret = {
                'username': db_username,
                'password': db_password,
                'dbname': db_name,
                'host': db_host,
                'port': db_port
            }
            
            return connection, secret
            
        # Fallback to Secrets Manager
        else:
            logger.info("Environment variables not found, falling back to Secrets Manager")
            db_secret_arn = os.environ['DB_SECRET_ARN']
            
            # Get database credentials from Secrets Manager
            secrets_client = boto3.client('secretsmanager')
            secret_response = secrets_client.get_secret_value(SecretId=db_secret_arn)
            secret = json.loads(secret_response['SecretString'])
            
            # Connect directly to Aurora cluster (not through RDS Proxy for migrations)
            cluster_endpoint = os.environ.get('DB_CLUSTER_ENDPOINT', 
                                             os.environ.get('DB_PROXY_ENDPOINT'))
            
            connection = psycopg2.connect(
                host=cluster_endpoint,
                database=secret.get('dbname', secret.get('engine', 'fitspace')),
                user=secret['username'],
                password=secret['password'],
                port=secret.get('port', 5432)
            )
            
            return connection, secret
        
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise


def run_migrations():
    """
    Run Alembic database migrations
    """
    try:
        # Get database connection
        connection, secret = get_database_connection()
        
        # Set up Alembic configuration
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        
        # Set the database URL for Alembic
        db_url = f"postgresql://{secret['username']}:{secret['password']}@{connection.info.host}:{connection.info.port}/{connection.info.dbname}"
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        # Run migrations
        print("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        print("✅ Migrations completed successfully")
        
        connection.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)


def create_migration(message):
    """
    Create a new migration
    """
    try:
        # Get database connection for URL
        connection, secret = get_database_connection()
        
        # Set up Alembic configuration
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        
        # Set the database URL for Alembic
        db_url = f"postgresql://{secret['username']}:{secret['password']}@{connection.info.host}:{connection.info.port}/{connection.info.dbname}"
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        # Create migration
        print(f"Creating migration: {message}")
        command.revision(alembic_cfg, message=message, autogenerate=True)
        print("✅ Migration created successfully")
        
        connection.close()
        
    except Exception as e:
        logger.error(f"Failed to create migration: {str(e)}")
        print(f"❌ Failed to create migration: {str(e)}")
        sys.exit(1)


def init_database():
    """
    Initialize the database with basic tables
    """
    try:
        connection, _ = get_database_connection()
        cursor = connection.cursor()
        
        # Create basic tables
        print("Creating initial database schema...")
        
        # Users table with additional fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(20),
                bio TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
        """)
        
        # Function to automatically update updated_at timestamp
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        # Trigger to automatically update updated_at
        cursor.execute("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
            CREATE TRIGGER update_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """)
        
        # Insert some sample data (optional)
        cursor.execute("""
            INSERT INTO users (name, email, phone, bio) VALUES 
            ('John Doe', 'john@example.com', '+1-555-0123', 'Software developer passionate about fitness'),
            ('Jane Smith', 'jane@example.com', '+1-555-0124', 'Personal trainer and nutrition coach')
            ON CONFLICT (email) DO NOTHING;
        """)
        
        connection.commit()
        print("✅ Database schema created successfully")
        print("✅ Sample data inserted")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        print(f"❌ Failed to initialize database: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage.py migrate          # Run migrations")
        print("  python manage.py makemigration <message>  # Create new migration")
        print("  python manage.py init             # Initialize database")
        sys.exit(1)
    
    command_arg = sys.argv[1]
    
    if command_arg == "migrate":
        run_migrations()
    elif command_arg == "makemigration":
        if len(sys.argv) < 3:
            print("Please provide a migration message")
            sys.exit(1)
        create_migration(sys.argv[2])
    elif command_arg == "init":
        init_database()
    else:
        print(f"Unknown command: {command_arg}")
        sys.exit(1)
