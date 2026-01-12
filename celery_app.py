from celery import Celery
from src.config import settings

app = Celery(
    'robinhood_app',
    broker=settings.redis_url.replace("redis://", "redis://") + '/0',  # Use Redis as broker
    backend=settings.redis_url + '/1',
    include=['stockr_backbone.src.fetcher']
)

app.conf.task_routes = {
    'fetch_and_store': {'queue': 'fetching'}
}
