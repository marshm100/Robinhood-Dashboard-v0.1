"""
Test script to verify database persistence fix.

This script verifies that:
1. The database path is absolute (not relative)
2. The database file is created in a consistent location
3. Data persists across multiple operations
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_database_path_is_absolute():
    """Test that database URL uses absolute path"""
    from src.config import settings
    
    db_url = settings.database_url
    print(f"\n1. Testing Database URL:")
    print(f"   Database URL: {db_url}")
    
    # Check it's not a relative path
    assert "sqlite:///.\\" not in db_url and "sqlite:///./" not in db_url, \
        "Database URL should not use relative path '.'"
    
    # Extract path and verify it's absolute
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        path_obj = Path(db_path)
        print(f"   Database path: {path_obj}")
        print(f"   Is absolute: {path_obj.is_absolute()}")
        assert path_obj.is_absolute(), "Database path must be absolute"
    
    print("   [PASS] Database path is absolute")
    return True


def test_database_directory_exists():
    """Test that database directory can be created"""
    from src.config import settings
    
    db_url = settings.database_url
    print(f"\n2. Testing Database Directory:")
    
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        path_obj = Path(db_path)
        parent_dir = path_obj.parent
        
        print(f"   Parent directory: {parent_dir}")
        print(f"   Directory exists: {parent_dir.exists()}")
        
        # Create if doesn't exist
        parent_dir.mkdir(parents=True, exist_ok=True)
        assert parent_dir.exists(), "Failed to create database directory"
    
    print("   [PASS] Database directory exists or was created")
    return True


def test_database_operations():
    """Test basic database CRUD operations"""
    from src.database import SessionLocal, init_db_sync
    from src.models import Transaction
    from datetime import date
    
    print(f"\n3. Testing Database Operations:")
    
    # Initialize database
    init_db_sync()
    
    # Create a session
    db = SessionLocal()
    
    try:
        # Count existing transactions
        initial_count = db.query(Transaction).count()
        print(f"   Initial transaction count: {initial_count}")
        
        # Insert a test transaction (using correct model fields)
        test_transaction = Transaction(
            activity_date=str(date.today()),
            ticker="TEST_PERSIST",
            trans_code="Test",
            quantity=1.0,
            price=100.0,
            amount=100.0
        )
        
        db.add(test_transaction)
        db.commit()
        
        # Verify it was inserted
        new_count = db.query(Transaction).count()
        print(f"   After insert count: {new_count}")
        assert new_count == initial_count + 1, "Insert failed"
        
        # Query it back
        test_record = db.query(Transaction).filter(
            Transaction.ticker == "TEST_PERSIST"
        ).first()
        
        assert test_record is not None, "Failed to retrieve test record"
        print(f"   Retrieved record: {test_record.ticker}")
        
        # Clean up - delete test transaction
        db.delete(test_record)
        db.commit()
        
        final_count = db.query(Transaction).count()
        print(f"   After cleanup count: {final_count}")
        assert final_count == initial_count, "Cleanup failed"
        
    finally:
        db.close()
    
    print("   [PASS] Database CRUD operations work correctly")
    return True


def test_session_independence():
    """Test that data persists across different sessions"""
    from src.database import SessionLocal, init_db_sync
    from src.models import Transaction
    from datetime import date
    
    print(f"\n4. Testing Session Independence:")
    
    # Initialize database
    init_db_sync()
    
    # Session 1: Insert data
    db1 = SessionLocal()
    try:
        test_transaction = Transaction(
            activity_date=str(date.today()),
            ticker="SESSION_TEST",
            trans_code="Test",
            quantity=1.0,
            price=200.0,
            amount=200.0
        )
        db1.add(test_transaction)
        db1.commit()
        test_id = test_transaction.id
        print(f"   Session 1: Inserted record with ID {test_id}")
    finally:
        db1.close()
    
    # Session 2: Query data (simulates navigating to another page)
    db2 = SessionLocal()
    try:
        record = db2.query(Transaction).filter(
            Transaction.ticker == "SESSION_TEST"
        ).first()
        
        assert record is not None, "Record not found in new session!"
        print(f"   Session 2: Found record - {record.ticker} (ID: {record.id})")
        
        # Clean up
        db2.delete(record)
        db2.commit()
        print(f"   Session 2: Cleaned up test record")
    finally:
        db2.close()
    
    print("   [PASS] Data persists across different sessions")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("DATABASE PERSISTENCE TEST")
    print("=" * 60)
    
    all_passed = True
    
    try:
        test_database_path_is_absolute()
    except AssertionError as e:
        print(f"   [FAIL] {e}")
        all_passed = False
    except Exception as e:
        print(f"   [ERROR] {e}")
        all_passed = False
    
    try:
        test_database_directory_exists()
    except AssertionError as e:
        print(f"   [FAIL] {e}")
        all_passed = False
    except Exception as e:
        print(f"   [ERROR] {e}")
        all_passed = False
    
    try:
        test_database_operations()
    except AssertionError as e:
        print(f"   [FAIL] {e}")
        all_passed = False
    except Exception as e:
        print(f"   [ERROR] {e}")
        all_passed = False
    
    try:
        test_session_independence()
    except AssertionError as e:
        print(f"   [FAIL] {e}")
        all_passed = False
    except Exception as e:
        print(f"   [ERROR] {e}")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - Database persistence is working!")
    else:
        print("SOME TESTS FAILED - Check output above")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
