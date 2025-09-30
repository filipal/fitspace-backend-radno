#!/bin/bash

# Debug script to test the API endpoint and see what's happening

echo "=== API Endpoint Debug Test ==="

# Test both endpoints to see what's happening
API_URL="https://or2k2645m5.execute-api.eu-central-1.amazonaws.com/prod"

echo ""
echo "1. Testing basic status endpoint:"
echo "curl -v \"${API_URL}/status\""
echo ""

# Test with verbose output to see what's happening
curl -v -m 30 "${API_URL}/status" 2>&1 | head -20

echo ""
echo "================================"
echo ""
echo "2. Testing with just status code:"
response_code=$(curl -s -o /dev/null -w "%{http_code}" -m 30 "${API_URL}/status")
echo "HTTP Response Code: ${response_code}"

echo ""
echo "3. Testing response body (if any):"
response_body=$(curl -s -m 30 "${API_URL}/status")
echo "Response Body: ${response_body}"

echo ""
echo "4. Testing response structure:"
echo "${response_body}" | jq . 2>/dev/null || echo "Response is not valid JSON"

echo ""
echo "5. Checking if 'success' field exists:"
echo "${response_body}" | jq -r '.success' 2>/dev/null || echo "No 'success' field found"

echo ""
echo "=== End Debug Test ==="
