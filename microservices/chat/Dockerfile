FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5004
# Production server. Single worker + threads (JSON files / in-memory chat state).
CMD ["sh", "-c", "gunicorn -w 1 --threads 100 -b 0.0.0.0:${PORT:-5004} app:app"]
