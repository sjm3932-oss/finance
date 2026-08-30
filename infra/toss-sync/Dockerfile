FROM python:3.12-slim
WORKDIR /app
COPY infra/toss-sync/requirements-toss-worker.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY scripts/toss_client.py scripts/sync_toss.py scripts/toss_sync_worker.py /app/scripts/
ENV PYTHONUNBUFFERED=1
CMD ["python3", "scripts/toss_sync_worker.py"]
