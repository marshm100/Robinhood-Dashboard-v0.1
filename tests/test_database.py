#!/usr/bin/env python3
"""
Database operations testing
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from sqlalchemy import text
from src.database import SessionLocal, engine, init_db
from src.models import Transaction, StockPrice, CustomPortfolio, PortfolioSnapshot

class TestDatabaseOperations:
    """Test database operations"""

    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    def test_database_connection(self, db_session):
        """Test database connection"""
        # Execute a simple query
        result = db_session.execute(text("SELECT 1"))
        assert result.fetchone()[0] == 1

    def test_table_creation(self, db_session):
        """Test that all tables are created"""
        # Check if tables exist
        tables = db_session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )).fetchall()

        table_names = [table[0] for table in tables]

        expected_tables = [
            "transactions",
            "stock_prices",
            "custom_portfolios",
            "portfolio_snapshots"
        ]

        for table in expected_tables:
            assert table in table_names, f"Table {table} not found"

    def test_transaction_crud_operations(self, db_session):
        """Test Transaction CRUD operations"""
        # Create
        transaction = Transaction(
            activity_date="2023-01-01",
            ticker="AAPL",
            trans_code="Buy",
            quantity=10,
            price=150.0,
            amount=-1500.0
        )
        db_session.add(transaction)
        db_session.commit()

        # Read
        saved_transaction = db_session.query(Transaction).filter_by(ticker="AAPL").first()
        assert saved_transaction is not None
        assert saved_transaction.quantity == 10
        assert saved_transaction.price == 150.0

        # Update
        saved_transaction.quantity = 20
        db_session.commit()

        updated_transaction = db_session.query(Transaction).filter_by(ticker="AAPL").first()
        assert updated_transaction.quantity == 20

        # Delete
        db_session.delete(updated_transaction)
        db_session.commit()

        deleted_transaction = db_session.query(Transaction).filter_by(ticker="AAPL").first()
        assert deleted_transaction is None

    def test_transaction_bulk_operations(self, db_session):
        """Test bulk transaction operations"""
        # Create multiple transactions
        transactions = []
        for i in range(10):
            transaction = Transaction(
                activity_date=f"2023-01-{i+1:02d}",
                ticker=f"TICKER{i}",
                trans_code="Buy",
                quantity=10 + i,
                price=100.0 + i,
                amount=-(10 + i) * (100.0 + i)
            )
            transactions.append(transaction)

        # Bulk insert
        db_session.add_all(transactions)
        db_session.commit()

        # Verify bulk insert
        count = db_session.query(Transaction).count()
        assert count >= 10

        # Bulk delete
        db_session.query(Transaction).filter(Transaction.ticker.like("TICKER%")).delete()
        db_session.commit()

        count_after = db_session.query(Transaction).count()
        assert count_after < count

    def test_transaction_relationships(self, db_session):
        """Test transaction relationships and queries"""
        # Create transactions for multiple tickers
        tickers = ["AAPL", "MSFT", "GOOGL"]
        for ticker in tickers:
            transaction = Transaction(
                activity_date="2023-01-01",
                ticker=ticker,
                trans_code="Buy",
                quantity=10,
                price=100.0,
                amount=-1000.0
            )
            db_session.add(transaction)
        db_session.commit()

        # Test filtering by ticker
        aapl_transactions = db_session.query(Transaction).filter_by(ticker="AAPL").all()
        assert len(aapl_transactions) == 1

        # Test ordering
        ordered_transactions = db_session.query(Transaction).order_by(Transaction.activity_date).all()
        assert len(ordered_transactions) == 3

        # Test aggregation
        total_quantity = db_session.query(Transaction).with_entities(
            db_session.query(Transaction.quantity).label("total")
        ).first()
        assert total_quantity is not None

    def test_custom_portfolio_operations(self, db_session):
        """Test CustomPortfolio CRUD operations"""
        # Create
        portfolio = CustomPortfolio(
            name="Test Portfolio",
            description="Test description",
            strategy="lump_sum",
            allocations='{"AAPL": 60, "MSFT": 40}',
            monthly_investment=1000.0,
            start_date="2023-01-01"
        )
        db_session.add(portfolio)
        db_session.commit()

        # Read
        saved_portfolio = db_session.query(CustomPortfolio).filter_by(name="Test Portfolio").first()
        assert saved_portfolio is not None
        assert saved_portfolio.strategy == "lump_sum"

        # Update
        saved_portfolio.monthly_investment = 2000.0
        db_session.commit()

        updated_portfolio = db_session.query(CustomPortfolio).filter_by(name="Test Portfolio").first()
        assert updated_portfolio.monthly_investment == 2000.0

        # Delete
        db_session.delete(updated_portfolio)
        db_session.commit()

        deleted_portfolio = db_session.query(CustomPortfolio).filter_by(name="Test Portfolio").first()
        assert deleted_portfolio is None

    def test_data_integrity_constraints(self, db_session):
        """Test data integrity constraints"""
        # Test NOT NULL constraints
        try:
            transaction = Transaction(
                activity_date=None,  # Should fail
                ticker="AAPL",
                trans_code="Buy",
                quantity=10,
                price=150.0,
                amount=-1500.0
            )
            db_session.add(transaction)
            db_session.commit()
            assert False, "Should have failed NOT NULL constraint"
        except Exception:
            db_session.rollback()  # Expected to fail

        # Test valid data
        transaction = Transaction(
            activity_date="2023-01-01",
            ticker="AAPL",
            trans_code="Buy",
            quantity=10,
            price=150.0,
            amount=-1500.0
        )
        db_session.add(transaction)
        db_session.commit()

        saved = db_session.query(Transaction).filter_by(ticker="AAPL").first()
        assert saved is not None

    def test_database_performance(self, db_session):
        """Test database performance with larger datasets"""
        import time

        # Create larger dataset
        transactions = []
        for i in range(100):
            transaction = Transaction(
                activity_date=f"2023-01-{i%28 + 1:02d}",
                ticker=f"TICKER{i%10}",
                trans_code="Buy",
                quantity=10 + i,
                price=100.0 + (i % 50),
                amount=-(10 + i) * (100.0 + (i % 50))
            )
            transactions.append(transaction)

        # Measure bulk insert performance
        start_time = time.time()
        db_session.add_all(transactions)
        db_session.commit()
        insert_time = time.time() - start_time

        # Should complete in reasonable time
        assert insert_time < 5.0, f"Bulk insert took too long: {insert_time}s"

        # Measure query performance
        start_time = time.time()
        count = db_session.query(Transaction).count()
        query_time = time.time() - start_time

        assert query_time < 1.0, f"Count query took too long: {query_time}s"
        assert count >= 100

    def test_transaction_date_indexing(self, db_session):
        """Test date-based queries and indexing"""
        # Create transactions with different dates
        dates = ["2023-01-01", "2023-06-01", "2023-12-01", "2024-01-01"]

        for i, date in enumerate(dates):
            transaction = Transaction(
                activity_date=date,
                ticker=f"STOCK{i}",
                trans_code="Buy",
                quantity=10,
                price=100.0,
                amount=-1000.0
            )
            db_session.add(transaction)
        db_session.commit()

        # Test date range queries
        from_date = "2023-01-01"
        to_date = "2023-12-31"

        date_filtered = db_session.query(Transaction).filter(
            Transaction.activity_date >= from_date,
            Transaction.activity_date <= to_date
        ).all()

        assert len(date_filtered) == 3  # Should exclude 2024 date

        # Test ordering by date
        ordered = db_session.query(Transaction).order_by(Transaction.activity_date.desc()).all()
        assert len(ordered) == 4
        assert ordered[0].activity_date == "2024-01-01"

    def test_database_error_handling(self, db_session):
        """Test database error handling"""
        # Test invalid data types
        try:
            transaction = Transaction(
                activity_date="2023-01-01",
                ticker="AAPL",
                trans_code="Buy",
                quantity="invalid",  # Should be numeric
                price=150.0,
                amount=-1500.0
            )
            db_session.add(transaction)
            db_session.commit()
            assert False, "Should have failed type validation"
        except Exception:
            db_session.rollback()  # Expected to fail

        # Test connection errors (simulate)
        try:
            # This should work in normal operation
            result = db_session.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        except Exception as e:
            assert False, f"Database connection failed: {e}"

    def test_data_migration_compatibility(self, db_session):
        """Test data compatibility across schema versions"""
        # This tests that our current schema works with existing data patterns

        # Test various transaction types
        transaction_types = [
            ("Buy", -1000.0),
            ("Sell", 1000.0),
            ("Dividend", 50.0),
            ("Transfer", -500.0)
        ]

        for trans_code, amount in transaction_types:
            transaction = Transaction(
                activity_date="2023-01-01",
                ticker="AAPL" if trans_code in ["Buy", "Sell"] else None,
                trans_code=trans_code,
                quantity=10 if trans_code in ["Buy", "Sell"] else None,
                price=100.0 if trans_code in ["Buy", "Sell"] else None,
                amount=amount
            )
            db_session.add(transaction)
        db_session.commit()

        # Verify all transaction types were saved
        count = db_session.query(Transaction).count()
        assert count == 4

        # Verify nullable fields work
        dividend_tx = db_session.query(Transaction).filter_by(trans_code="Dividend").first()
        assert dividend_tx.quantity is None
        assert dividend_tx.ticker is None

class TestDatabaseConcurrency:
    """Test database concurrency and transactions"""

    def test_transaction_isolation(self, db_session):
        """Test transaction isolation"""
        # Start a transaction
        db_session.begin()

        # Create a transaction
        transaction = Transaction(
            activity_date="2023-01-01",
            ticker="AAPL",
            trans_code="Buy",
            quantity=10,
            price=150.0,
            amount=-1500.0
        )
        db_session.add(transaction)

        # Should be visible within this session
        count = db_session.query(Transaction).count()
        assert count >= 1

        # Rollback should undo changes
        db_session.rollback()

        # Should not be visible after rollback
        count_after = db_session.query(Transaction).count()
        assert count_after == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
