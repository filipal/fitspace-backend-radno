"""
Test suite for the backend API
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.routes import api_routes
from src.utils.response import create_response, create_error_response
from src.utils.database import execute_query


class TestAPIRoutes:
    """Test API route handlers"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_connection = Mock()
        self.mock_cursor = Mock()
        self.mock_connection.cursor.return_value = self.mock_cursor
    
    def test_status_endpoint_success(self):
        """Test successful status endpoint"""
        # Mock database query
        self.mock_cursor.description = [('health_check',)]
        self.mock_cursor.fetchall.return_value = [(1,)]
        
        event = {
            'path': '/status',
            'httpMethod': 'GET'
        }
        
        with patch('src.routes.api_routes.execute_query') as mock_execute:
            mock_execute.return_value = [{'health_check': 1}]
            
            response = api_routes.handle_request(event, self.mock_connection)
            
            assert response['statusCode'] == 200
            response_body = json.loads(response['body'])
            assert response_body['success'] is True
            assert response_body['data']['status'] == 'healthy'
    
    def test_status_endpoint_database_error(self):
        """Test that basic status endpoint doesn't fail even with database issues"""
        event = {
            'path': '/status',
            'httpMethod': 'GET'
        }
        
        # Even with database connection issues, basic status should work
        with patch('src.routes.api_routes.execute_query') as mock_execute:
            mock_execute.side_effect = Exception("Database connection failed")
            
            response = api_routes.handle_request(event, self.mock_connection)
            
            # Basic status endpoint should still return 200 (doesn't use database)
            assert response['statusCode'] == 200
            response_body = json.loads(response['body'])
            assert response_body['success'] is True
            assert response_body['data']['status'] == 'healthy'
            assert response_body['data']['database'] == 'not_tested'
    
    def test_status_db_endpoint_database_error(self):
        """Test database status endpoint with database error"""
        event = {
            'path': '/status/db',
            'httpMethod': 'GET'
        }
        
        # Mock database connection failure for /status/db endpoint
        with patch('src.utils.database.get_database_connection_with_retry') as mock_get_db:
            mock_get_db.side_effect = Exception("Database connection failed")
            
            response = api_routes.handle_request(event, None)  # No connection provided
            
            assert response['statusCode'] == 503
            response_body = json.loads(response['body'])
            assert 'Database connection failed' in response_body['error']
    
    def test_cors_preflight(self):
        """Test CORS preflight request"""
        event = {
            'path': '/api/v1/users',
            'httpMethod': 'OPTIONS'
        }
        
        with patch('src.routes.api_routes.create_response') as mock_create_response:
            mock_create_response.return_value = {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'CORS preflight'})
            }
            
            response = api_routes.handle_request(event, self.mock_connection)
            
            mock_create_response.assert_called_once_with(200, {'message': 'CORS preflight'})
    
    def test_get_users_endpoint(self):
        """Test get users endpoint"""
        event = {
            'path': '/api/v1/users',
            'httpMethod': 'GET',
            'queryStringParameters': {'limit': '5', 'offset': '0'}
        }
        
        mock_users = [
            {'id': 1, 'name': 'John Doe', 'email': 'john@example.com', 'created_at': '2023-01-01'},
            {'id': 2, 'name': 'Jane Smith', 'email': 'jane@example.com', 'created_at': '2023-01-02'}
        ]
        
        # Mock database query
        with patch('src.routes.api_routes.User') as mock_user_class:
            mock_user_instance = Mock()
            mock_user_class.return_value = mock_user_instance
            mock_user_instance.get_all.return_value = mock_users
            mock_user_instance.count.return_value = 2
            
            response = api_routes.handle_request(event, self.mock_connection)
            
            assert response['statusCode'] == 200
            response_body = json.loads(response['body'])
            assert response_body['success'] is True
            assert len(response_body['data']) == 2
    
    def test_create_user_endpoint(self):
        """Test create user endpoint"""
        event = {
            'path': '/api/v1/users',
            'httpMethod': 'POST',
            'body': json.dumps({
                'name': 'New User',
                'email': 'newuser@example.com'
            })
        }
        
        mock_user = {
            'id': 3,
            'name': 'New User',
            'email': 'newuser@example.com',
            'created_at': '2023-01-03'
        }
        
        with patch('src.routes.api_routes.User') as mock_user_class:
            mock_user_instance = Mock()
            mock_user_class.return_value = mock_user_instance
            mock_user_instance.create.return_value = mock_user
            
            response = api_routes.handle_request(event, self.mock_connection)
            
            assert response['statusCode'] == 200
            response_body = json.loads(response['body'])
            assert response_body['success'] is True
            assert response_body['data']['name'] == 'New User'
    
    def test_create_user_missing_data(self):
        """Test create user with missing required data"""
        event = {
            'path': '/api/v1/users',
            'httpMethod': 'POST',
            'body': json.dumps({
                'name': 'Incomplete User'
                # Missing email
            })
        }
        
        response = api_routes.handle_request(event, self.mock_connection)
        
        assert response['statusCode'] == 400
        response_body = json.loads(response['body'])
        assert 'Name and email are required' in response_body['error']
    
    def test_get_single_user(self):
        """Test get single user endpoint"""
        event = {
            'path': '/api/v1/users/1',
            'httpMethod': 'GET'
        }

        mock_user = {
            'id': 1,
            'name': 'John Doe',
            'email': 'john@example.com',
            'created_at': '2023-01-01'
        }
        
        with patch('src.routes.api_routes.User') as mock_user_class, \
            patch('src.routes.api_routes.Avatar') as mock_avatar_class:
            mock_user_instance = Mock()
            mock_user_class.return_value = mock_user_instance
            mock_user_instance.get_by_id.return_value = mock_user

            mock_avatar_instance = Mock()
            mock_avatar_class.return_value = mock_avatar_instance
            mock_avatar_instance.list_for_user.return_value = [{'id': 2, 'display_name': 'Default'}]

            response = api_routes.handle_request(event, self.mock_connection)
            
            assert response['statusCode'] == 200
            response_body = json.loads(response['body'])
            assert response_body['data']['id'] == 1
            assert response_body['data']['avatars'] == [{'id': 2, 'display_name': 'Default'}]

    def test_get_single_user_not_found(self):
        """Test get single user that doesn't exist"""
        event = {
            'path': '/api/v1/users/999',
            'httpMethod': 'GET'
        }
        
        with patch('src.routes.api_routes.User') as mock_user_class:
            mock_user_instance = Mock()
            mock_user_class.return_value = mock_user_instance
            mock_user_instance.get_by_id.return_value = []
            
            response = api_routes.handle_request(event, self.mock_connection)
            
            assert response['statusCode'] == 404
            response_body = json.loads(response['body'])
            assert 'User not found' in response_body['error']
    
    def test_invalid_route(self):
        """Test invalid route returns 404"""
        event = {
            'path': '/api/v1/invalid',
            'httpMethod': 'GET'
        }
        
        response = api_routes.handle_request(event, self.mock_connection)
        
        assert response['statusCode'] == 404
        response_body = json.loads(response['body'])
        assert 'Route not found' in response_body['error']


class TestDatabaseUtilities:
    """Test database utility functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_connection = Mock()
        self.mock_cursor = Mock()
        self.mock_connection.cursor.return_value = self.mock_cursor
    
    @patch.dict('os.environ', {
        'DB_SECRET_ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test',
        'DB_PROXY_ENDPOINT': 'test-proxy.proxy-123456789012.us-east-1.rds.amazonaws.com'
    })
    @patch('boto3.client')
    @patch('psycopg2.connect')
    def test_get_database_connection_success(self, mock_psycopg2, mock_boto3):
        """Test successful database connection"""
        # Mock AWS Secrets Manager
        mock_secrets_client = Mock()
        mock_boto3.return_value = mock_secrets_client
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'username': 'testuser',
                'password': 'testpass',
                'dbname': 'testdb',
                'port': 5432
            })
        }
        
        # Mock psycopg2 connection
        mock_conn = Mock()
        mock_psycopg2.return_value = mock_conn
        
        from src.utils.database import get_database_connection
        
        connection = get_database_connection()
        
        assert connection is not None
        mock_psycopg2.assert_called_once()


class TestResponseUtilities:
    """Test response utility functions"""
    
    def test_create_response(self):
        """Test create_response function"""
        response = create_response(200, {'message': 'success'})
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        
        body = json.loads(response['body'])
        assert body['message'] == 'success'
    
    def test_create_error_response(self):
        """Test create_error_response function"""
        response = create_error_response(400, 'Bad request', 'Invalid data')
        
        assert response['statusCode'] == 400
        
        body = json.loads(response['body'])
        assert body['error'] == 'Bad request'
        assert body['details'] == 'Invalid data'


if __name__ == '__main__':
    pytest.main([__file__])
