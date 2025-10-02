# FitSpace Backend - Quick Start Guide

## 🚀 What You've Built

You now have a complete serverless backend with:

### ✅ **User Management API** with full CRUD operations:
- **GET** `/api/v1/users` - List users with pagination & search
- **POST** `/api/v1/users` - Create new users
- **GET** `/api/v1/users/{id}` - Get specific user
- **PUT** `/api/v1/users/{id}` - Update user
- **DELETE** `/api/v1/users/{id}` - Delete user
- **GET** `/api/v1/users/search?q=term` - Search users

### ✅ **Database Features**:
- PostgreSQL with proper schema
- Automatic timestamps (created_at, updated_at)
- Data validation
- Search functionality
- Pagination support

### ✅ **Production Ready**:
- Comprehensive error handling
- Logging
- Unit tests
- CI/CD pipeline
- AWS integration

## 🏃‍♂️ **Quick Start - Local Development**

### **Step 1: Set Up Local Environment**
```bash
# Clone and navigate to project
git clone https://github.com/e-kipica/fitspace-backend.git
cd fitspace-backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### **Step 2: Set Environment Variables**
```bash
# Replace with your actual AWS credentials
export DB_SECRET_ARN="arn:aws:secretsmanager:eu-central-1:027728694574:secret:pixel-streaming-db-credentials-drsymw"

# Default behaviour (via RDS Proxy)
export DB_PROXY_ENDPOINT="pixel-streaming-rds-proxy.proxy-chku4sk8sd1x.eu-central-1.rds.amazonaws.com"

# Optional: point directly to the Aurora cluster (skips the proxy)
# export DB_CLUSTER_ENDPOINT="pixel-streaming.cluster-chku4sk8sd1x.eu-central-1.rds.amazonaws.com"

# Optional: provide explicit connection details instead of Secrets Manager
# export DB_HOST="localhost"
# export DB_NAME="fitspace"
# export DB_USERNAME="postgres"
# export DB_PASSWORD="postgres"
# export DB_PORT="5432"
```
> ℹ️ When both `DB_CLUSTER_ENDPOINT` and `DB_PROXY_ENDPOINT` are set, the backend will prefer
> the cluster endpoint. If no cluster endpoint is available, it will fall back to the host
> stored in the secret (if present) or the proxy endpoint.

### **Step 3: Start Development Server**
```bash
# Start the Flask development server
python3 dev_server.py
```

You should see:
```
🚀 FitSpace Backend Development Server
📍 Running on http://localhost:3000
📮 Use Postman with base URL: http://localhost:3000
```

### **Step 4: Test with Postman**

#### **Import Collection**
1. Open Postman
2. Import → Upload → Select `postman_collection.json`
3. Set Environment: `base_url = http://localhost:3000`

#### **Test These Endpoints:**

**✅ Health Check** (Works even without DB permissions):
```
GET http://localhost:3000/status
```

**✅ Input Validation** (Works perfectly):
```
POST http://localhost:3000/api/v1/users
Content-Type: application/json

{
    "name": "Test User",
    "email": "invalid-email"  // Invalid format
}
```
Expected: `400 Bad Request` with validation error

**✅ Missing Fields** (Works perfectly):
```
POST http://localhost:3000/api/v1/users
Content-Type: application/json

{
    "name": "Test User"  // Missing email
}
```
Expected: `400 Bad Request` - "Name and email are required"

**✅ Route Handling** (Works perfectly):
```
GET http://localhost:3000/api/v1/invalid-route
```
Expected: `404 Not Found` - "Route not found"

**⚠️ Database Operations** (Will show permission errors but API works):
```
POST http://localhost:3000/api/v1/users
Content-Type: application/json

{
    "name": "John Doe",
    "email": "john@fitspace.com",
    "phone": "+1-555-0123",
    "bio": "Fitness enthusiast"
}
```
Expected: `500 Internal Error` with AWS permissions details (this is normal!)

## 🚀 **Deployment to AWS**

### **Option 1: Automatic Deployment (Recommended)**

#### **Step 1: Set Up GitHub Secrets**
Go to your repository → Settings → Secrets and Variables → Actions

Add these secrets:
```
AWS_REGION = eu-central-1
AWS_ROLE_ARN = arn:aws:iam::YOUR-ACCOUNT:role/github-actions-role
S3_BUCKET_NAME = your-lambda-code-bucket
LAMBDA_FUNCTION_NAME = pixel-streaming-backend-handler
API_GATEWAY_URL = https://your-api-id.execute-api.eu-central-1.amazonaws.com/prod
```

#### **Step 2: Deploy**
```bash
# Commit and push to main branch
git add .
git commit -m "Deploy FitSpace backend"
git push origin main
```

GitHub Actions will automatically:
- ✅ Run tests
- ✅ Build deployment package
- ✅ Upload to S3
- ✅ Update Lambda function
- ✅ Test the deployment

#### **Step 3: Test Production API**
Update your Postman environment:
- `base_url = https://your-api-id.execute-api.eu-central-1.amazonaws.com/prod`

Test the same endpoints as local development!

### **Option 2: Manual Deployment**

#### **Step 1: Create Deployment Package**
```bash
# Ensure you're in virtual environment
source venv/bin/activate

# Create deployment package
mkdir -p package
pip install -r requirements.txt -t ./package
cp -r src ./package/
cp app.py ./package/

# Create zip file
cd package
zip -r ../deployment.zip . -x "*.pyc" "*/__pycache__/*" "*/tests/*"
cd ..
```

#### **Step 2: Upload to Lambda**
```bash
# Upload to S3 (replace with your bucket)
aws s3 cp deployment.zip s3://your-lambda-bucket/backend/latest.zip

# Update Lambda function (replace with your function name)
aws lambda update-function-code \
  --function-name pixel-streaming-backend-handler \
  --s3-bucket your-lambda-bucket \
  --s3-key backend/latest.zip

# Wait for update
aws lambda wait function-updated \
  --function-name pixel-streaming-backend-handler
```

#### **Step 3: Test Deployment**
```bash
# Test via API Gateway (replace with your URL)
curl https://your-api-id.execute-api.eu-central-1.amazonaws.com/prod/status
```

### **Step 4: Initialize Database** (First deployment only)
```bash
# Set environment variables for your deployed environment
export DB_SECRET_ARN="your-deployed-secret-arn"
export DB_PROXY_ENDPOINT="your-deployed-proxy-endpoint"
export AWS_DEFAULT_REGION=eu-central-1

# Initialize database schema
python3 migrations/manage.py init
```

## 📮 **Testing Production with Postman**

Once deployed, update your Postman collection:

### **Environment Variables:**
- `base_url = https://your-api-gateway-url.amazonaws.com/prod`
- `api_version = v1`

### **Test All Endpoints:**
1. **GET** `{{base_url}}/status` - Health check
2. **GET** `{{base_url}}/api/{{api_version}}/users` - List users
3. **POST** `{{base_url}}/api/{{api_version}}/users` - Create user
4. **GET** `{{base_url}}/api/{{api_version}}/users/1` - Get user
5. **PUT** `{{base_url}}/api/{{api_version}}/users/1` - Update user
6. **DELETE** `{{base_url}}/api/{{api_version}}/users/1` - Delete user
7. **GET** `{{base_url}}/api/{{api_version}}/users/search?q=john` - Search users

### **Expected Results:**
- ✅ All validation still works (400 errors for invalid input)
- ✅ Database operations work (if permissions are set up)
- ✅ CORS headers present
- ✅ Proper error handling

## 🔍 **Monitoring Deployment**

### **Check Logs:**
```bash
# View Lambda logs
aws logs tail /aws/lambda/pixel-streaming-backend-handler --follow

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/pixel-streaming-backend-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### **Test Health:**
```bash
# Quick health check
curl -f https://your-api-gateway-url/prod/status || echo "Health check failed"
```

## 🛠 Next Steps - How to Use & Extend

### 1. **Test the API Locally** (without database)
```bash
# Show API documentation
python test_local.py docs

# Test with mock responses (shows API structure)
python test_local.py
```

### 2. **Set Up Database Connection** (when you have infrastructure)
```bash
# Set environment variables
export DB_SECRET_ARN="arn:aws:secretsmanager:region:account:secret:your-secret"
export DB_PROXY_ENDPOINT="your-proxy-endpoint.proxy-xxx.region.rds.amazonaws.com"

# Initialize database schema
python migrations/manage.py init

# Test real database connection
python -c "
import sys
sys.path.append('src')
from utils.database import get_database_connection
try:
    conn = get_database_connection()
    print('✅ Database connected!')
    conn.close()
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

### 3. **Start Development Environment & Test with Postman**

#### **Step 1: Set Up Virtual Environment**
```bash
# Create virtual environment (if not exists)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install boto3 psycopg2-binary flask flask-cors
```

#### **Step 2: Set Environment Variables**
```bash
# Set your AWS database credentials
export DB_SECRET_ARN="arn:aws:secretsmanager:region:account:secret:your-secret"
export DB_PROXY_ENDPOINT="your-proxy-endpoint.proxy-xxx.region.rds.amazonaws.com"

# Test database connection (optional - may fail due to permissions)
python3 test_db_connection.py
```

#### **Step 3: Start Development Server**
```bash
# Start the Flask development server
python3 dev_server.py
```

**You should see:**
```
🚀 FitSpace Backend Development Server
📍 Running on http://localhost:3000
📚 API Documentation: http://localhost:3000/status
🧪 Test with: python test_local.py
📮 Use Postman with base URL: http://localhost:3000

💡 Available endpoints:
   GET  /status                           - Health check
   GET  /api/v1/users                     - List users
   POST /api/v1/users                     - Create user
   GET  /api/v1/users/{id}                - Get user
   PUT  /api/v1/users/{id}                - Update user
   DELETE /api/v1/users/{id}              - Delete user
   GET  /api/v1/users/search?q=term       - Search users
```

#### **Step 4: Test with Postman**

**A. Set Up Postman Collection:**

1. **Open Postman**
2. **Import Collection**: Import the `postman_collection.json` file from your project
3. **Create Environment**: 
   - Name: "FitSpace Local"
   - Variables:
     - `base_url` = `http://localhost:3000`
     - `api_version` = `v1`

**B. Test These Endpoints (Even Without Database Access):**

**✅ 1. Health Check** - Should work, may show database error but API structure is correct:
```
GET {{base_url}}/status
```

**✅ 2. Test Input Validation** - These work perfectly without database:

*Invalid Email Format:*
```
POST {{base_url}}/api/{{api_version}}/users
Content-Type: application/json

{
    "name": "Test User",
    "email": "invalid-email"
}
```
Expected: `400 Bad Request` with validation error

*Missing Required Fields:*
```
POST {{base_url}}/api/{{api_version}}/users
Content-Type: application/json

{
    "name": "Test User"
}
```
Expected: `400 Bad Request` - "Name and email are required"

*Valid User Creation:*
```
POST {{base_url}}/api/{{api_version}}/users
Content-Type: application/json

{
    "name": "John Doe",
    "email": "john.doe@fitspace.com", 
    "phone": "+1-555-0123",
    "bio": "Fitness enthusiast"
}
```
Expected: `500 Internal Server Error` (database connection issue, but validation passes)

**✅ 3. Test Route Handling:**

*Invalid Route:*
```
GET {{base_url}}/api/{{api_version}}/invalid-route
```
Expected: `404 Not Found` - "Route not found"

*CORS Preflight:*
```
OPTIONS {{base_url}}/api/{{api_version}}/users
```
Expected: `200 OK` with CORS headers

**✅ 4. Test Parameter Validation:**

*Invalid User ID:*
```
GET {{base_url}}/api/{{api_version}}/users/abc
```
Expected: `400 Bad Request` - "Invalid user ID format"

*Search without query:*
```
GET {{base_url}}/api/{{api_version}}/users/search
```
Expected: `400 Bad Request` - "Search term is required"

#### **Step 5: What You're Testing**

Even without database access, you can verify:

- ✅ **Input validation** (email format, required fields)
- ✅ **JSON parsing** (malformed JSON handling)  
- ✅ **Route handling** (404 for invalid routes)
- ✅ **Parameter validation** (invalid IDs, missing search terms)
- ✅ **HTTP methods** (GET, POST, PUT, DELETE)
- ✅ **CORS handling** (OPTIONS requests)
- ✅ **Error responses** (proper status codes and messages)

#### **Step 6: Monitor Server Logs**

In your terminal where `dev_server.py` is running, watch real-time request logs:
```
127.0.0.1 - - [09/Sep/2025 10:30:15] "GET /status HTTP/1.1" 200 -
127.0.0.1 - - [09/Sep/2025 10:30:20] "POST /api/v1/users HTTP/1.1" 500 -
127.0.0.1 - - [09/Sep/2025 10:30:25] "POST /api/v1/users HTTP/1.1" 400 -
```

### 4. **Run Unit Tests**
```bash
# Install dependencies first
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific tests
pytest tests/test_status.py -v
```

### 5. **Add New Endpoints** 

To add new functionality (e.g., workouts, exercises), follow this pattern:

**Step 1:** Create a new model in `src/models/`
```python
# src/models/workout.py
class Workout:
    def __init__(self, connection):
        self.connection = connection
    
    def get_all(self, user_id, limit=10, offset=0):
        # Implementation
        pass
    
    def create(self, user_id, name, exercises):
        # Implementation  
        pass
```

**Step 2:** Add routes in `src/routes/api_routes.py`
```python
# In handle_v1_routes function, add:
elif route == '/workouts' and method == 'GET':
    return get_workouts(event, connection)
elif route == '/workouts' and method == 'POST':
    return create_workout(event, connection)

# Then implement the functions
def get_workouts(event, connection):
    workout_model = Workout(connection)
    # Implementation
    pass
```

**Step 3:** Add database schema in `migrations/manage.py`
```python
# In init_database function:
cursor.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        name VARCHAR(200) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
""")
```

**Step 4:** Add tests in `tests/`
```python
# tests/test_workouts.py
def test_create_workout():
    # Test implementation
    pass
```

### 5. **Common API Patterns You Can Use**

The codebase provides these reusable patterns:

**Pagination:**
```python
return create_paginated_response(
    data=items,
    page=page,
    limit=limit,
    total_count=total_count
)
```

**Error Handling:**
```python
try:
    # Your logic
    return create_success_response(data, message)
except ValueError as e:
    return create_error_response(400, str(e))
except Exception as e:
    return create_error_response(500, 'Internal error', str(e))
```

**Database Queries:**
```python
# Simple query
users = execute_query(connection, "SELECT * FROM users WHERE id = %s", (user_id,))

# Query with no return
execute_query(connection, "DELETE FROM users WHERE id = %s", (user_id,), fetch=False)
```

### 6. **Deployment to AWS**

Once your infrastructure is ready:

1. **Set GitHub Secrets** (as documented in README.md)
2. **Push to main branch** - triggers automatic deployment
3. **Monitor in CloudWatch** - check logs and metrics

### 7. **API Examples You Can Try**

```bash
# Health check
curl https://your-api-gateway-url/prod/status

# List users  
curl https://your-api-gateway-url/prod/api/v1/users?limit=5

# Create user
curl -X POST https://your-api-gateway-url/prod/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@fitspace.com", "bio": "Fitness enthusiast"}'

# Update user
curl -X PUT https://your-api-gateway-url/prod/api/v1/users/1 \
  -H "Content-Type: application/json" \
  -d '{"bio": "Updated bio text"}'

# Search users
curl "https://your-api-gateway-url/prod/api/v1/users/search?q=john&limit=10"

# Get specific user
curl https://your-api-gateway-url/prod/api/v1/users/1
```

### 8. **File Structure Reference**

```
src/
├── models/           # Database models (User, Workout, Exercise, etc.)
│   └── user.py      ✅ Complete user model with CRUD operations
├── routes/          # API endpoint handlers
│   └── api_routes.py ✅ All user endpoints implemented
└── utils/           # Utilities
    ├── database.py  ✅ DB connection & query utilities
    └── response.py  ✅ Standardized HTTP responses

tests/               ✅ Comprehensive test suite
migrations/          ✅ Database schema management
.github/workflows/   ✅ CI/CD pipeline
```
