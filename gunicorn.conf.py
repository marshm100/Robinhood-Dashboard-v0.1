# Gunicorn configuration for production deployment

import multiprocessing
import os

# Server socket - Railway uses PORT env var
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes - limit for Railway's resource constraints
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeout - increased for slow startup
timeout = 120
keepalive = 10
graceful_timeout = 30

# Logging
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "robinhood-dashboard"

# Server mechanics
preload_app = False  # Disable preload to avoid import issues
pidfile = None  # No pidfile needed in container
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None
