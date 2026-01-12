"""
Comprehensive Browser Functionality Test
Tests all features of the application including CSV upload, analysis, and switching between files
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"
CSV_FILE_1 = Path("354e8757-62f9-506c-9b30-db3ac6d907e8.csv")
CSV_FILE_2 = Path(r"c:\Users\Marshall\Downloads\354e8757-62f9-506c-9b30-db3ac6d907e8.csv")

def test_endpoint(url, description, expected_status=200):
    """Test an API endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == expected_status:
            print(f"[PASS] {description}")
            try:
                data = response.json()
                print(f"Response keys: {list(data.keys())[:10]}")
                return True, data
            except:
                print(f"Response: {response.text[:200]}")
                return True, response.text
        else:
            print(f"[FAIL] Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False, None
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False, None

def upload_csv(file_path, description):
    """Upload a CSV file"""
    print(f"\n{'='*60}")
    print(f"Uploading CSV: {description}")
    print(f"File: {file_path}")
    print(f"{'='*60}")
    
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return False, None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/csv')}
            response = requests.post(f"{BASE_URL}/api/upload-csv", files=files, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"[PASS] CSV uploaded successfully")
            data = response.json()
            print(f"Transactions processed: {data.get('transactions_processed', 'N/A')}")
            return True, data
        else:
            print(f"[FAIL] Upload failed")
            print(f"Response: {response.text[:500]}")
            return False, None
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

def test_all_features():
    """Test all features of the application"""
    results = {
        'csv_upload_1': False,
        'csv_upload_2': False,
        'portfolio_overview': False,
        'portfolio_history': False,
        'performance_metrics': False,
        'risk_assessment': False,
        'advanced_analytics': False,
        'analysis_page': False,
        'comparison_page': False,
    }
    
    print("="*60)
    print("COMPREHENSIVE BROWSER FUNCTIONALITY TEST")
    print("="*60)
    
    # Test 1: Upload first CSV file
    print("\n\nPHASE 1: Upload First CSV File")
    success, data = upload_csv(CSV_FILE_1, "First CSV File (workspace root)")
    results['csv_upload_1'] = success
    
    if not success:
        print("\n⚠️  WARNING: First CSV upload failed. Continuing with tests anyway...")
    
    # Wait for processing
    time.sleep(2)
    
    # Test 2: Test all API endpoints after first upload
    print("\n\nPHASE 2: Test All Features After First Upload")
    
    success, data = test_endpoint(f"{BASE_URL}/api/portfolio-overview", "Portfolio Overview")
    results['portfolio_overview'] = success
    
    success, data = test_endpoint(f"{BASE_URL}/api/portfolio-history", "Portfolio History")
    results['portfolio_history'] = success
    
    success, data = test_endpoint(f"{BASE_URL}/api/performance-metrics", "Performance Metrics")
    results['performance_metrics'] = success
    
    success, data = test_endpoint(f"{BASE_URL}/api/risk-assessment", "Risk Assessment")
    results['risk_assessment'] = success
    
    success, data = test_endpoint(f"{BASE_URL}/api/advanced-analytics", "Advanced Analytics")
    results['advanced_analytics'] = success
    
    # Test 3: Test web pages
    print("\n\nPHASE 3: Test Web Pages")
    
    try:
        response = requests.get(f"{BASE_URL}/analysis", timeout=30)
        results['analysis_page'] = response.status_code == 200
        status = "[PASS]" if results['analysis_page'] else "[FAIL]"
        print(f"Analysis Page: {status} (Status: {response.status_code})")
    except Exception as e:
        print(f"Analysis Page: [ERROR] {e}")
    
    try:
        response = requests.get(f"{BASE_URL}/comparison", timeout=30)
        results['comparison_page'] = response.status_code == 200
        status = "[PASS]" if results['comparison_page'] else "[FAIL]"
        print(f"Comparison Page: {status} (Status: {response.status_code})")
    except Exception as e:
        print(f"Comparison Page: [ERROR] {e}")
    
    # Test 4: Upload second CSV file (switching)
    print("\n\nPHASE 4: Upload Second CSV File (Switching)")
    success, data = upload_csv(CSV_FILE_2, "Second CSV File (Downloads folder)")
    results['csv_upload_2'] = success
    
    if not success:
        print("\n⚠️  WARNING: Second CSV upload failed.")
    
    # Wait for processing
    time.sleep(2)
    
    # Test 5: Verify data switched correctly
    print("\n\nPHASE 5: Verify Data Switched Correctly")
    
    success, data = test_endpoint(f"{BASE_URL}/api/portfolio-overview", "Portfolio Overview (After Switch)")
    if success and data:
        transaction_count = data.get('transaction_count', 0)
        print(f"Transaction count after switch: {transaction_count}")
    
    success, data = test_endpoint(f"{BASE_URL}/api/portfolio-history", "Portfolio History (After Switch)")
    
    # Summary
    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name:30} {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    return results

if __name__ == "__main__":
    test_all_features()

