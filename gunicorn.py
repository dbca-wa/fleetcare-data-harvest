import os
import multiprocessing

dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv

    load_dotenv()

# Gunicorn configuration settings.
port = os.getenv("PORT", 8080)
bind = f":{port}"
# Don't start too many workers:
workers = min(multiprocessing.cpu_count(), 4)
# Give workers an expiry:
max_requests = 2048
max_requests_jitter = 256
preload_app = True
# Disable access logging.
accesslog = None
