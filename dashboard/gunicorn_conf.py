"""Gunicorn configuration for production deployment."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 2
threads = 4
worker_class = "gthread"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Pre-load app for faster worker startup
preload_app = True

def post_fork(server, worker):
    """Start auto-resolve thread after fork."""
    from dashboard.app import _start_resolver
    _start_resolver()
