# FitSpace Backend

A serverless backend API built with Python and AWS Lambda, designed to work with the [backend infrastructure module](https://github.com/your-org/fitspace-infrastructure).

## Architecture

This backend is designed as a serverless application that runs on AWS Lambda and connects to Aurora PostgreSQL via RDS Proxy. The architecture supports:

- **AWS Lambda**: Serverless compute for API endpoints
- **Aurora PostgreSQL Serverless v2**: Auto-scaling database
- **RDS Proxy**: Connection pooling and management  
- **API Gateway**: REST API routing and management
- **Secrets Manager**: Secure credential storage
- **S3**: Lambda deployment package storage

## Project Structure

```
fitspace-backend/
├── app.py                 # Main Lambda handler
├── requirements.txt       # Python dependencies
├── .github/
│   └── workflows/
│       └── deploy.yml     # GitHub Actions CI/CD
├── src/
│   ├── __init__.py
│   ├── models/            # Data models (future)
│   │   └── __init__.py
│   ├── routes/            # API route handlers
│   │   ├── __init__.py
│   │   └── api_routes.py
│   └── utils/             # Utility functions
│       ├── __init__.py
│       ├── database.py    # Database connection utilities
│       └── response.py    # HTTP response utilities
├── tests/                 # Unit tests
│   ├── conftest.py        # Pytest configuration
│   ├── test_status.py     # API endpoint tests
│   └── test_lambda_handler.py  # Lambda handler tests
└── migrations/            # Database migrations
    └── manage.py          # Migration management script
```

## Getting Started

### Prerequisites

- Python 3.11+
- AWS CLI configured with appropriate permissions
- Access to the deployed infrastructure (Aurora, Lambda, etc.)

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/e-kipica/fitspace-backend.git
   cd fitspace-backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables for local testing:**
   ```bash
   export DB_SECRET_ARN="arn:aws:secretsmanager:region:account:secret:your-secret"
   export DB_PROXY_ENDPOINT="your-proxy-endpoint.proxy-xxx.region.rds.amazonaws.com"
   ```

### Development Workflow - Adding Features & Testing

#### 1. **Adding New API Endpoints**

Follow this pattern to add new features (e.g., workouts, exercises):

**Step 1: Create a Model** (in `src/models/`)
```python
# src/models/workout.py
from src.utils.database import execute_query
import logging

logger = logging.getLogger(__name__)

class Workout:
    def __init__(self, connection):
        self.connection = connection
    
    def get_by_user_id(self, user_id, limit=10, offset=0):
        """Get workouts for a specific user"""
        try:
            workouts = execute_query(
                self.connection,
                """
                SELECT id, user_id, name, description, created_at, updated_at 
                FROM workouts 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset)
            )
            return workouts
        except Exception as e:
            logger.error(f"Error getting workouts: {str(e)}")
            raise
    
    def create(self, user_id, name, description=None):
        """Create a new workout"""
        try:
            result = execute_query(
                self.connection,
                """
                INSERT INTO workouts (user_id, name, description, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING id, user_id, name, description, created_at, updated_at
                """,
                (user_id, name, description)
            )
            self.connection.commit()
            return result[0]
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error creating workout: {str(e)}")
            raise
```

**Step 2: Add Routes** (in `src/routes/api_routes.py`)
```python
# Import your new model at the top
from src.models.workout import Workout

# In handle_v1_routes function, add new route handlers:
elif route.startswith('/users/') and route.endswith('/workouts') and method == 'GET':
    user_id = route.split('/')[2]  # Extract user_id from /users/{id}/workouts
    return get_user_workouts(user_id, event, connection)
elif route.startswith('/users/') and route.endswith('/workouts') and method == 'POST':
    user_id = route.split('/')[2]
    return create_user_workout(user_id, event, connection)

# Add the handler functions at the end of the file:
def get_user_workouts(user_id, event, connection):
    """Get workouts for a specific user"""
    try:
        user_id_int = int(user_id)
        query_params = event.get('queryStringParameters') or {}
        limit = min(int(query_params.get('limit', 10)), 100)
        offset = int(query_params.get('offset', 0))
        
        workout_model = Workout(connection)
        workouts = workout_model.get_by_user_id(user_id_int, limit, offset)
        
        return create_success_response(workouts, f'Retrieved {len(workouts)} workouts')
    except Exception as e:
        logger.error(f"Error getting user workouts: {str(e)}")
        return create_error_response(500, 'Failed to retrieve workouts', str(e))
```

**Step 3: Update Database Schema** (in `migrations/manage.py`)
```python
# In init_database function, add new table:
cursor.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_workouts_user_id ON workouts(user_id);
""")
```

#### 2. **Testing Your Changes**

**Option A: Local Testing Script**
```bash
# Test API structure without database
python test_local.py docs

# Test with your actual database (if connected)
python test_local.py
```

**Option B: Unit Tests**
```bash
# Run existing tests
pytest

# Run specific test file
pytest tests/test_status.py -v

# Add new test file for your feature
# tests/test_workouts.py
```

#### 3. **Testing with Postman**

**Setup Postman Environment:**

1. **Create New Collection**: "FitSpace Backend API"

2. **Set Environment Variables**:
   - `base_url`: `http://localhost:3000` (for SAM local) or your API Gateway URL
   - `api_version`: `v1`

3. **Test Endpoints**:

**Health Check:**
```
GET {{base_url}}/status
```

**Get Users (with pagination):**
```
GET {{base_url}}/api/{{api_version}}/users?limit=5&offset=0
```

**Create User:**
```
POST {{base_url}}/api/{{api_version}}/users
Headers: Content-Type: application/json
Body (raw JSON):
{
    "name": "John Doe",
    "email": "john.doe@example.com", 
    "phone": "+1-555-0123",
    "bio": "Fitness enthusiast and personal trainer"
}
```

**Get Specific User:**
```
GET {{base_url}}/api/{{api_version}}/users/1
```

**Update User:**
```
PUT {{base_url}}/api/{{api_version}}/users/1
Headers: Content-Type: application/json
Body (raw JSON):
{
    "name": "John Updated",
    "bio": "Updated bio text"
}
```

**Search Users:**
```
GET {{base_url}}/api/{{api_version}}/users/search?q=john&limit=10
```

**Delete User:**
```
DELETE {{base_url}}/api/{{api_version}}/users/1
```

**Your New Workout Endpoints:**
```
GET {{base_url}}/api/{{api_version}}/users/1/workouts
POST {{base_url}}/api/{{api_version}}/users/1/workouts
Body: {"name": "Morning Cardio", "description": "30min cardio workout"}
```

#### 4. **Local Development Server Options**

**Option A: AWS SAM Local** (Recommended for Lambda testing)
```bash
# Install SAM CLI first
pip install aws-sam-cli

# Create sam template (template.yaml) - basic example:
# AWSTemplateFormatVersion: '2010-09-09'
# Transform: AWS::Serverless-2016-10-31
# Resources:
#   FitSpaceApi:
#     Type: AWS::Serverless::Function
#     Properties:
#       CodeUri: ./
#       Handler: app.lambda_handler
#       Runtime: python3.11

# Start local API
sam local start-api --port 3000
```

**Option B: Simple Flask Wrapper** (Quick testing)
```python
# create dev_server.py
from flask import Flask, request, jsonify
from app import lambda_handler
import json

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def catch_all(path):
    # Convert Flask request to Lambda event format
    event = {
        'path': '/' + path if path else '/',
        'httpMethod': request.method,
        'headers': dict(request.headers),
        'queryStringParameters': dict(request.args) if request.args else None,
        'body': request.get_data(as_text=True) if request.data else None
    }
    
    # Call Lambda handler
    response = lambda_handler(event, None)
    
    # Return response
    return jsonify(json.loads(response['body'])), response['statusCode']

if __name__ == '__main__':
    app.run(debug=True, port=3000)
```

```bash
# Install Flask and run
pip install flask
python dev_server.py
```

#### 5. **Development Workflow Summary**

1. **Make Changes**: Edit files in `src/models/`, `src/routes/`, etc.
2. **Update Database**: Add schema changes in `migrations/manage.py`
3. **Test Locally**: 
   ```bash
   python test_local.py  # Quick structure test
   pytest                # Unit tests
   ```
4. **Test with Postman**: Use local server (SAM or Flask)
5. **Format Code**: `black src/ app.py`
6. **Commit & Push**: Triggers automatic deployment via GitHub Actions

#### 6. **Postman Collection Template**

You can import this JSON to get started:
```json
{
    "info": {"name": "FitSpace Backend API"},
    "variable": [
        {"key": "base_url", "value": "http://localhost:3000"},
        {"key": "api_version", "value": "v1"}
    ],
    "item": [
        {
            "name": "Health Check",
            "request": {
                "method": "GET",
                "url": "{{base_url}}/status"
            }
        },
        {
            "name": "Create User",
            "request": {
                "method": "POST",
                "url": "{{base_url}}/api/{{api_version}}/users",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"name\": \"John Doe\",\n    \"email\": \"john@example.com\",\n    \"bio\": \"Test user\"\n}"
                }
            }
        }
    ]
}
```

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_status.py -v
```

### Code Quality

```bash
# Format code
black src/ app.py

# Lint code
flake8 src/ app.py --max-line-length=100
```

## API Endpoints

### Health Check
- **GET** `/status` - Check API and database health

### Users (Example API)
- **GET** `/api/v1/users` - List all users
  - Query params: `limit`, `offset`
- **POST** `/api/v1/users` - Create a new user
  - Body: `{"name": "string", "email": "string"}`
- **GET** `/api/v1/users/{id}` - Get user by ID

### Example Requests

```bash
# Health check
curl https://your-api-gateway-url/prod/status

# Get users
curl https://your-api-gateway-url/prod/api/v1/users?limit=5&offset=0

# Create user
curl -X POST https://your-api-gateway-url/prod/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'
```

## Database Management

### Running Migrations

```bash
# Set required environment variables
export DB_SECRET_ARN="your-secret-arn"
export DB_CLUSTER_ENDPOINT="your-cluster-endpoint"

# Initialize database (first time only)
python migrations/manage.py init

# Run migrations
python migrations/manage.py migrate

# Create a new migration
python migrations/manage.py makemigration "add users table"
```

## Deployment

### GitHub Actions Setup

1. **Configure GitHub Secrets:**
   Go to your repository → Settings → Secrets and Variables → Actions

   | Secret Name | Description | Example |
   |-------------|-------------|---------|
   | `AWS_REGION` | AWS region | `us-east-1` |
   | `AWS_ROLE_ARN` | IAM role for GitHub Actions | `arn:aws:iam::123:role/github-actions-role` |
   | `S3_BUCKET_NAME` | S3 bucket for Lambda code | `my-project-lambda-code-123` |
   | `LAMBDA_FUNCTION_NAME` | Lambda function name | `pixel-streaming-backend-handler` |
   | `API_GATEWAY_URL` | Production API Gateway URL | `https://api123.execute-api.us-east-1.amazonaws.com/prod` |
   | `API_GATEWAY_URL_DEV` | Development API Gateway URL | `https://api456.execute-api.us-east-1.amazonaws.com/dev` |

2. **Deployment Triggers:**
   - Push to `main` branch → Deploy to production
   - Push to `develop` branch → Deploy to development
   - Pull requests → Run tests only

### Manual Deployment

```bash
# Create deployment package
mkdir -p package
pip install -r requirements.txt -t ./package
cp -r src ./package/
cp app.py ./package/

# Create zip file
cd package
zip -r ../deployment.zip . -x "*.pyc" "*/__pycache__/*"
cd ..

# Upload to S3
aws s3 cp deployment.zip s3://your-bucket/backend/latest.zip

# Update Lambda function
aws lambda update-function-code \
  --function-name your-function-name \
  --s3-bucket your-bucket \
  --s3-key backend/latest.zip

# Wait for update to complete
aws lambda wait function-updated --function-name your-function-name
```

## Environment Variables

The Lambda function uses these environment variables (set by the infrastructure):

- `DB_SECRET_ARN`: ARN of the Secrets Manager secret containing database credentials
- `DB_PROXY_ENDPOINT`: RDS Proxy endpoint for database connections
- `DB_CLUSTER_ENDPOINT`: (Optional) Direct Aurora cluster endpoint

## Monitoring and Logging

### CloudWatch Logs
- Lambda logs: `/aws/lambda/pixel-streaming-backend-handler`
- Use `aws logs tail` to monitor in real-time

### CloudWatch Metrics
- Lambda duration, errors, throttles
- API Gateway request count, latency, errors
- RDS Proxy connections, query duration

### Example Monitoring Commands

```bash
# Tail Lambda logs
aws logs tail /aws/lambda/pixel-streaming-backend-handler --follow

# Get recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/pixel-streaming-backend-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000

# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=pixel-streaming-backend-handler \
  --start-time $(date -d '24 hours ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average,Maximum
```

## Troubleshooting

### Common Issues

1. **Cold Start Latency**
   - Expected on first request after idle period
   - Monitor duration metrics to identify patterns

2. **Database Connection Errors**
   - Check RDS Proxy configuration
   - Verify security groups allow Lambda → RDS Proxy
   - Check Secrets Manager permissions

3. **Import Errors**
   - Ensure all dependencies are in the deployment package
   - Check Python path configuration

4. **CORS Issues**
   - Verify headers are set correctly in response utilities
   - Check API Gateway CORS configuration

### Debug Commands

```bash
# Test database connection
python -c "
import os
import sys
sys.path.append('src')
from utils.database import get_database_connection
try:
    conn = get_database_connection()
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

# Test API locally (requires sam-cli or similar)
sam local start-api

# Invoke function directly
aws lambda invoke \
  --function-name pixel-streaming-backend-handler \
  --payload '{"path":"/status","httpMethod":"GET"}' \
  response.json
```

## Contributing

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/new-feature`
3. **Write tests** for your changes
4. **Run the test suite:** `pytest`
5. **Format your code:** `black src/ app.py`
6. **Commit your changes:** `git commit -am 'Add new feature'`
7. **Push to the branch:** `git push origin feature/new-feature`
8. **Create a Pull Request**

### Code Standards

- Python 3.11+ compatible
- Follow PEP 8 style guidelines
- Write unit tests for new functionality
- Use type hints where applicable
- Document functions and classes with docstrings

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Infrastructure

This backend is designed to work with the [FitSpace Infrastructure](https://github.com/your-org/fitspace-infrastructure) Terraform module. See the infrastructure repository for deployment instructions.

## Support

For issues and questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review CloudWatch logs for error details
3. Verify infrastructure configuration
4. Create an issue in this repository
