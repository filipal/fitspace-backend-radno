#!/usr/bin/env python3
"""
Development server for local testing with Flask
This converts HTTP requests to Lambda event format for easy local testing
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import os

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from app import lambda_handler

app = Flask(__name__)
CORS(app)  # Enable CORS for all origins

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def catch_all(path):
    """
    Catch all routes and convert to Lambda event format
    """
    try:
        # Convert Flask request to Lambda event format
        event = {
            'path': ('/' + path) if path else '/',
            'httpMethod': request.method,
            'headers': dict(request.headers),
            'queryStringParameters': dict(request.args) if request.args else None,
            'body': request.get_data(as_text=True) if request.data else None,
            'isBase64Encoded': False,
            'requestContext': {
                'requestId': 'dev-request-id',
                'stage': 'dev'
            }
        }
        
        # Call Lambda handler
        response = lambda_handler(event, None)
        
        # Extract response data
        status_code = response.get('statusCode', 200)
        response_headers = response.get('headers', {})
        body = response.get('body', '{}')
        
        # Parse JSON body if possible
        try:
            body_json = json.loads(body)
            return jsonify(body_json), status_code, response_headers
        except:
            return body, status_code, response_headers
            
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist'
    }), 404

if __name__ == '__main__':
    print("🚀 FitSpace Backend Development Server")
    print("📍 Running on http://localhost:3000")
    print("📚 API Documentation: http://localhost:3000/status")
    print("🧪 Test with: python test_local.py")
    print("📮 Use Postman with base URL: http://localhost:3000")
    print("\n💡 Available endpoints:")
    print("   GET  /status                           - Health check")
    print("   GET  /api/v1/users                     - List users")
    print("   POST /api/v1/users                     - Create user")
    print("   GET  /api/v1/users/{id}                - Get user")
    print("   PUT  /api/v1/users/{id}                - Update user")
    print("   DELETE /api/v1/users/{id}              - Delete user")
    print("   GET  /api/v1/users/search?q=term       - Search users")
    print("\n🛑 Press Ctrl+C to stop\n")
    
    app.run(debug=True, host='0.0.0.0', port=3000)
