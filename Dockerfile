FROM python:3.11.9-slim@sha256:9e1912aab0a30bbd9488eb79063f68f42a68ab0946cbe98fecf197fe5b085506
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
USER nobody
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"]
