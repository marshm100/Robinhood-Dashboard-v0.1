import pytest
import time
from faker import Faker
from sqlalchemy import insert
from src.models import Transaction
from src.services.portfolio_calculator import PortfolioCalculator
from src.database import get_db

fake = Faker()

@pytest.mark.asyncio
async def test_large_dataset_performance():
    async with get_db() as db:
        # Generate 50000 fake transactions
        for _ in range(50000):
            await db.execute(insert(Transaction), {
                'activity_date': fake.date(),
                'ticker': fake.lexify('???'),
                'trans_code': 'Buy',
                'quantity': fake.random_number(),
                'price': fake.random_number(),
                'amount': fake.random_number()
            })
        await db.commit()
        
        calculator = PortfolioCalculator(db)
        start = time.time()
        metrics = await calculator.calculate_performance_metrics()  # Assume async version
        duration = time.time() - start
        assert duration < 1.2
