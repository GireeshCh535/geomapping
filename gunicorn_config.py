"""
Gunicorn configuration for high-concurrency tile serving
Optimized for 1000+ concurrent users
"""
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = int(os.getenv('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = 300
keepalive = 5

# Worker lifecycle
max_requests = 1000
max_requests_jitter = 100
preload_app = False  # Set to True if using connection pooling

# Logging: only errors to console (no per-request access logs)
accesslog = None  # Disable access log; set to "-" or a path to re-enable
errorlog = "-"
loglevel = os.getenv('LOG_LEVEL', 'error')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'geomapping'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed in future)
# keyfile = None
# certfile = None


