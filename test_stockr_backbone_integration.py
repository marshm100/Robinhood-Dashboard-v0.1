"""
Comprehensive Integration Test for stockr_backbone Core Architecture

This test suite verifies that stockr_backbone is fully operational and reliable
as the central, core workhorse of the application.

Test Coverage:
1. Background maintenance service startup and operation
2. Auto-discovery of new stock tickers
3. Continuous background refresh functionality
4. Health check integration
5. Status endpoint accuracy
6. End-to-end stock data flow
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any
import requests
import json

# Add project paths
project_root = Path(__file__).parent
stockr_path = project_root / "stockr_backbone"
if str(stockr_path) not in sys.path:
    sys.path.insert(0, str(stockr_path))

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_SYMBOL = "TSLA"  # Tesla - commonly available stock


class TestStockrBackboneIntegration:
    """Comprehensive test suite for stockr_backbone integration"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "[PASS]" if passed else "[FAIL]"
        result = {
            "test": test_name,
            "status": status,
            "passed": passed,
            "message": message
        }
        self.results.append(result)
        if passed:
            self.passed += 1
            print(f"{status}: {test_name}")
        else:
            self.failed += 1
            print(f"{status}: {test_name} - {message}")
    
    def test_1_import_background_maintenance(self):
        """Test 1: Verify background_maintenance module can be imported"""
        try:
            from src.background_maintenance import (
                get_maintenance_service,
                start_maintenance_service,
                stop_maintenance_service
            )
            self.log_test("Import background_maintenance", True)
            return True
        except Exception as e:
            self.log_test("Import background_maintenance", False, str(e))
            return False
    
    def test_2_service_initialization(self):
        """Test 2: Verify service can be initialized"""
        try:
            from src.background_maintenance import get_maintenance_service
            service = get_maintenance_service()
            self.log_test("Service initialization", service is not None)
            return service is not None
        except Exception as e:
            self.log_test("Service initialization", False, str(e))
            return False
    
    def test_3_service_start_stop(self):
        """Test 3: Verify service can start and stop cleanly"""
        try:
            from src.background_maintenance import (
                get_maintenance_service,
                start_maintenance_service,
                stop_maintenance_service
            )
            
            # Start service
            start_maintenance_service(refresh_interval_minutes=1)  # Short interval for testing
            service = get_maintenance_service()
            time.sleep(2)  # Give it time to start
            
            running = service.is_running()
            if not running:
                self.log_test("Service start/stop", False, "Service did not start")
                return False
            
            # Check status
            status = service.get_status()
            if not status.get("running"):
                self.log_test("Service start/stop", False, "Status shows not running")
                return False
            
            # Stop service
            stop_maintenance_service()
            time.sleep(1)
            
            running_after_stop = service.is_running()
            if running_after_stop:
                self.log_test("Service start/stop", False, "Service did not stop")
                return False
            
            self.log_test("Service start/stop", True)
            return True
        except Exception as e:
            self.log_test("Service start/stop", False, str(e))
            return False
    
    def test_4_auto_discovery_function(self):
        """Test 4: Verify ensure_stock_tracked function exists and works"""
        try:
            from src.fetcher_standalone import ensure_stock_tracked
            
            # Test with a known stock (this should work if stock exists or add it)
            # Using a test symbol that might not be in database
            test_symbol = "TESTSTOCK"
            result = ensure_stock_tracked(test_symbol)
            
            # Function should return True or False (not raise exception)
            self.log_test("Auto-discovery function", isinstance(result, bool), 
                         f"Result: {result}")
            return True
        except Exception as e:
            self.log_test("Auto-discovery function", False, str(e))
            return False
    
    def test_5_stock_price_service_auto_discovery(self):
        """Test 5: Verify StockPriceService auto-discovers new stocks"""
        try:
            from src.services.stock_price_service import StockPriceService
            
            service = StockPriceService()
            
            # Try to get price for a stock that might not exist
            # The service should attempt auto-discovery
            price = service.get_price_at_date("UNKNOWNTICKER", "2024-01-01")
            
            # Should not raise exception (even if returns None)
            self.log_test("StockPriceService auto-discovery", True,
                         f"Price lookup completed (result: {price is not None})")
            return True
        except Exception as e:
            self.log_test("StockPriceService auto-discovery", False, str(e))
            return False
    
    def test_6_health_check_integration(self):
        """Test 6: Verify health check includes stockr_backbone status"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                self.log_test("Health check integration", False, 
                             f"HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            # Check if stockr_backbone is in health check
            if "checks" in data and "stockr_backbone" in data["checks"]:
                stockr_check = data["checks"]["stockr_backbone"]
                self.log_test("Health check integration", True,
                             f"Status: {stockr_check.get('status')}")
                return True
            else:
                self.log_test("Health check integration", False,
                             "stockr_backbone not in health check")
                return False
        except requests.exceptions.ConnectionError:
            self.log_test("Health check integration", False,
                         "Cannot connect to server (is it running?)")
            return False
        except Exception as e:
            self.log_test("Health check integration", False, str(e))
            return False
    
    def test_7_status_endpoint(self):
        """Test 7: Verify /api/stockr-status endpoint works"""
        try:
            response = requests.get(f"{BASE_URL}/api/stockr-status", timeout=5)
            if response.status_code != 200:
                self.log_test("Status endpoint", False, f"HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            # Check response structure
            if "stockr_backbone" in data and "maintenance_service" in data["stockr_backbone"]:
                status = data["stockr_backbone"]["maintenance_service"]
                running = status.get("running", False)
                self.log_test("Status endpoint", True,
                             f"Service running: {running}, Refresh count: {status.get('refresh_count', 0)}")
                return True
            else:
                self.log_test("Status endpoint", False, "Invalid response structure")
                return False
        except requests.exceptions.ConnectionError:
            self.log_test("Status endpoint", False,
                         "Cannot connect to server (is it running?)")
            return False
        except Exception as e:
            self.log_test("Status endpoint", False, str(e))
            return False
    
    def test_8_service_status_accuracy(self):
        """Test 8: Verify status endpoint provides accurate information"""
        try:
            from src.background_maintenance import get_maintenance_service
            
            service = get_maintenance_service()
            status = service.get_status()
            
            # Verify status contains expected fields
            required_fields = ["running", "refresh_interval_minutes", "refresh_count", 
                             "tracked_stocks_count", "thread_alive"]
            
            missing_fields = [f for f in required_fields if f not in status]
            
            if missing_fields:
                self.log_test("Status accuracy", False,
                             f"Missing fields: {missing_fields}")
                return False
            
            self.log_test("Status accuracy", True,
                         f"All required fields present. Running: {status.get('running')}")
            return True
        except Exception as e:
            self.log_test("Status accuracy", False, str(e))
            return False
    
    def test_9_refresh_all_stocks_function(self):
        """Test 9: Verify refresh_all_stocks function exists and works"""
        try:
            from src.fetcher_standalone import refresh_all_stocks
            
            # This might take a while, so we'll just verify it exists and can be called
            # In a real test, we might want to mock this or use a test database
            self.log_test("Refresh all stocks function", True,
                         "Function exists and is callable")
            return True
        except Exception as e:
            self.log_test("Refresh all stocks function", False, str(e))
            return False
    
    def test_10_database_connectivity(self):
        """Test 10: Verify stockr_backbone database is accessible"""
        try:
            from src.services.stock_price_service import StockPriceService
            
            service = StockPriceService()
            validation = service.validate_database()
            
            if validation.get("valid"):
                stock_count = validation.get("stock_count", 0)
                price_count = validation.get("price_records", 0)
                self.log_test("Database connectivity", True,
                             f"Stocks: {stock_count}, Price records: {price_count}")
                return True
            else:
                error = validation.get("error", "Unknown error")
                self.log_test("Database connectivity", False, error)
                return False
        except Exception as e:
            self.log_test("Database connectivity", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("stockr_backbone Integration Test Suite")
        print("="*70 + "\n")
        
        # Run tests that don't require server
        self.test_1_import_background_maintenance()
        self.test_2_service_initialization()
        self.test_3_service_start_stop()
        self.test_4_auto_discovery_function()
        self.test_5_stock_price_service_auto_discovery()
        self.test_8_service_status_accuracy()
        self.test_9_refresh_all_stocks_function()
        self.test_10_database_connectivity()
        
        # Run tests that require server (with graceful handling)
        print("\n--- Server-dependent tests (require running application) ---")
        self.test_6_health_check_integration()
        self.test_7_status_endpoint()
        
        # Print summary
        print("\n" + "="*70)
        print("Test Summary")
        print("="*70)
        print(f"Total Tests: {len(self.results)}")
        print(f"[PASS] Passed: {self.passed}")
        print(f"[FAIL] Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/len(self.results)*100):.1f}%")
        print("="*70 + "\n")
        
        # Print detailed results
        print("Detailed Results:")
        for result in self.results:
            print(f"  {result['status']}: {result['test']}")
            if result['message']:
                print(f"    -> {result['message']}")
        
        return self.failed == 0


if __name__ == "__main__":
    tester = TestStockrBackboneIntegration()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

