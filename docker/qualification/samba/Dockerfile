FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends samba python3 && rm -rf /var/lib/apt/lists/*
COPY start.py /start.py
CMD ["python3", "/start.py"]
