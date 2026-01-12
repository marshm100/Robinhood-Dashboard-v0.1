#!/usr/bin/env python3
"""
Check if the Robinhood Portfolio Analysis app is running
"""

import requests

print('🔍 Checking if Robinhood Portfolio Analysis app is running...')
print()

try:
    response = requests.get('http://localhost:8000/health', timeout=3)
    if response.status_code == 200:
        print('✅ App is already running!')
        health_data = response.json()
        print(f'   Status: {health_data.get("status", "unknown")}')
        print(f'   Version: {health_data.get("version", "unknown")}')
        print(f'   Environment: {health_data.get("environment", "unknown")}')
        print()
        print('🌐 Access your app at:')
        print('   📊 Dashboard: http://localhost:8000/dashboard')
        print('   📤 Upload CSV: http://localhost:8000/upload')
        print('   🛠️  API Docs: http://localhost:8000/api/docs')
        print('   💚 Health Check: http://localhost:8000/health')
        print()
        print('🎯 Ready to analyze your Robinhood portfolio!')
    else:
        print(f'❌ App returned status code: {response.status_code}')

except requests.exceptions.RequestException as e:
    print(f'❌ App does not appear to be running: {e}')
    print()
    print('🚀 Starting the app...')
    print('Command: python run.py')























