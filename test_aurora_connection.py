#!/usr/bin/env python3
import requests
import json

# Database connection details
db_config = {
    "host": "aurora-dev.soho.kor.apac.npr.aws.asurion.net",
    "port": 3306,
    "user": "giho.seong",
    "password": "Asurion2023!",
    "database": "soho"
}

# Test the connection
url = "http://localhost:8000/api/v1/database/test"
headers = {"Content-Type": "application/json"}

print("Testing Aurora MySQL connection...")
print(f"Host: {db_config['host']}")
print(f"User: {db_config['user']}")
print("-" * 50)

try:
    response = requests.post(url, json=db_config, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Connection successful!")
        print(f"Database: {result.get('database', 'N/A')}")
        print(f"Version: {result.get('version', 'N/A')}")
        print(f"Message: {result.get('message', 'N/A')}")
    else:
        print(f"❌ Connection failed! Status: {response.status_code}")
        print(f"Error: {response.json()}")
        
except Exception as e:
    print(f"❌ Request failed: {str(e)}")