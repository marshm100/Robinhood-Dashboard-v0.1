#!/usr/bin/env python3
"""
Check the status of the running Robinhood Portfolio Analysis app
"""

import requests
import json

print('📊 Robinhood Portfolio Analysis - System Status')
print('=' * 55)

try:
    response = requests.get('http://localhost:8000/health', timeout=5)
    health_data = response.json()

    print('💚 HEALTH CHECK:')
    print(f'   Status: {health_data.get("status", "unknown")}')
    print(f'   Version: {health_data.get("version", "unknown")}')
    print(f'   Environment: {health_data.get("environment", "unknown")}')
    print()

    checks = health_data.get('checks', {})
    print('🔧 SERVICE STATUS:')
    for service, status_info in checks.items():
        status = status_info.get('status', 'unknown')
        message = status_info.get('message', '')

        if status == 'ok':
            print(f'   ✅ {service}: {message}')
        elif status == 'warning':
            print(f'   ⚠️  {service}: {message}')
        else:
            print(f'   ❌ {service}: {message}')

    print()
    print('🚀 APPLICATION READY!')
    print('Visit http://localhost:8000 in your browser')
    print()
    print('🌐 Access URLs:')
    print('   📊 Dashboard: http://localhost:8000/dashboard')
    print('   📤 Upload CSV: http://localhost:8000/upload')
    print('   🛠️  API Docs: http://localhost:8000/api/docs')
    print('   💚 Health Check: http://localhost:8000/health')
    print('   📈 Monitoring: http://localhost:8000/monitoring/dashboard')

except Exception as e:
    print(f'❌ Error getting health status: {e}')
    print()
    print('💡 Troubleshooting:')
    print('   1. Make sure the app is running: python run.py')
    print('   2. Check if port 8000 is available')
    print('   3. Look for error messages in the terminal')
