"""
Unit tests for the Lambda handler
"""
import pytest
import json
from unittest.mock import Mock, patch
from app import lambda_handler


class TestLambdaHandler:
    """Test the main Lambda handler function"""
    
    @patch('app.get_database_connection_with_retry')
    @patch('app.api_routes.handle_request')
    def test_lambda_handler_success(self, mock_handle_request, mock_get_db):
        """Test successful Lambda handler execution"""
        # Mock database connection
        mock_connection = Mock()
        mock_get_db.return_value = mock_connection
        
        # Mock API response
        mock_handle_request.return_value = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': True, 'data': 'test'})
        }
        
        # Test event (non-status endpoint that requires DB)
        event = {
            'path': '/api/v1/users',
            'httpMethod': 'GET'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        mock_connection.close.assert_called_once()
    
    def test_lambda_handler_cors_preflight(self):
        """Test CORS preflight handling - no DB connection needed"""
        event = {
            'httpMethod': 'OPTIONS'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should return CORS response without touching database
        assert response['statusCode'] == 200
        assert 'CORS preflight' in response['body']
    
    def test_lambda_handler_status_endpoint(self):
        """Test status endpoint - no DB connection needed"""
        event = {
            'path': '/status',
            'httpMethod': 'GET'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should return success without database connection
        assert response['statusCode'] == 200
        response_body = json.loads(response['body'])
        assert response_body['success'] is True
        assert response_body['data']['status'] == 'healthy'
        assert response_body['data']['database'] == 'not_tested'
    
    @patch('app.get_database_connection_with_retry')
    @patch('app.api_routes.handle_request')
    def test_lambda_handler_error(self, mock_handle_request, mock_get_db):
        """Test Lambda handler with error"""
        # Mock database connection
        mock_connection = Mock()
        mock_get_db.return_value = mock_connection
        
        # Mock API error
        mock_handle_request.side_effect = Exception("Test error")
        
        event = {
            'path': '/api/v1/test',
            'httpMethod': 'GET'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 500
        assert 'error' in response['body']
        mock_connection.close.assert_called_once()
    
    @patch('app.get_database_connection_with_retry')
    def test_lambda_handler_database_connection_error(self, mock_get_db):
        """Test Lambda handler with database connection error"""
        # Mock database connection failure
        mock_get_db.side_effect = Exception("Database connection failed")
        
        event = {
            'path': '/api/v1/test',
            'httpMethod': 'GET'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 500
        assert 'error' in response['body']


if __name__ == '__main__':
    pytest.main([__file__])
