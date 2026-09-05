# Gunicorn-django settings
bind = ["0.0.0.0:8000"]
name = "drive"
python_path = "/app"

# Run
graceful_timeout = 90
timeout = 90
workers = 3

# Logging
# Using '-' for the access log file makes gunicorn log accesses to stdout
accesslog = "-"
# Paths only: signed query strings and authorization data must never be logged.
access_log_format = '%(h)s %(t)s "%(m)s %(H)s" %(s)s %(b)s %(L)s'
# Using '-' for the error log file makes gunicorn log errors to stderr
errorlog = "-"
loglevel = "info"
