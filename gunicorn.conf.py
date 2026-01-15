# Gunicorn configuration for production deployment

import os

# Worker processes - handled by CMD
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeout
timeout = 120 # Explicitly set in CMD as well
keepalive = 10
graceful_timeout = 30

# Logging
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = "-" # Explicitly set in CMD as well
errorlog = "-"  # Explicitly set in CMD as well
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "robinhood-dashboard"

# Server mechanics
preload_app = False
pidfile = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None
