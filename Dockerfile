FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY streamlit_app ./streamlit_app
COPY .streamlit ./.streamlit

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PORT=8501

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
