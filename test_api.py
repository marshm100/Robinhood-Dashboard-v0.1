#!/usr/bin/env python3
"""
Test API endpoints
"""

import requests

def test_endpoint(url, description):
    try:
        print(f"\n=== Testing {description} ===")
        response = requests.get(url)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Success! Response type: {type(data)}")
            if isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
                if 'transactions' in data:
                    print(f"Transactions count: {len(data['transactions'])}")
                    if data['transactions']:
                        print(f"Sample transaction: {data['transactions'][0]}")
                elif 'has_data' in data:
                    print(f"Has data: {data['has_data']}")
                elif 'history' in data:
                    print(f"History points: {len(data['history'])}")
            elif isinstance(data, list):
                print(f"List length: {len(data)}")
        else:
            print(f"Error response: {response.text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    base_url = "http://localhost:8000"

    test_endpoint(f"{base_url}/api/transactions?limit=5", "Transactions endpoint")
    test_endpoint(f"{base_url}/api/portfolio-overview", "Portfolio overview endpoint")
    test_endpoint(f"{base_url}/api/portfolio-history", "Portfolio history endpoint")
