# Gunicorn configuration for AI Anime Dating Backend
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
backlog = 2048

# Worker processes
workers = 1  # Start with 1 worker for resource management
worker_class = "sync"
worker_connections = 1000
timeout = 120  # Worker timeout in seconds (increased from default 30)
keepalive = 2

# Restart workers after this many requests, this can prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Process naming
proc_name = "ai-anime-dating"

# Server mechanics
preload_app = True
pidfile = "/tmp/gunicorn.pid"
