#!/usr/bin/env python3
import requests
import sys
import os

# Define the URL to check - uses environment variable PORT or defaults to 8000
port = os.environ.get("PORT", 8000)
url = f"http://localhost:{port}/health"

try:
    # Make a request to the health endpoint
    response = requests.get(url, timeout=5)
    
    # Check if response is successful
    if response.status_code == 200:
        print(f"Health check passed: {response.json()}")
        sys.exit(0)  # Exit with success code
    else:
        print(f"Health check failed: HTTP {response.status_code}")
        sys.exit(1)  # Exit with error code
except Exception as e:
    print(f"Health check failed: {str(e)}")
    sys.exit(1)  # Exit with error code 