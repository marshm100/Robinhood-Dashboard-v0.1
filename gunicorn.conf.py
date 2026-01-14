# Gunicorn configuration for production deployment

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeout
timeout = 30
keepalive = 10
graceful_timeout = 30

# Logging
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = os.getenv("LOG_FILE", "-")
errorlog = os.getenv("LOG_FILE", "-")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "robinhood-dashboard"

# Server mechanics
preload_app = True
pidfile = "./data/gunicorn.pid"
user = "app"
group = "app"
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None

# Application
wsgi_module = None
callable = None
application_path = "src.main:app"
