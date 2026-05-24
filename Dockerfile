FROM dockerhub.timeweb.cloud/library/node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

WORKDIR /app

COPY . /app
COPY --from=frontend-build /frontend/dist/static/index.css /app/static/index.css
COPY --from=frontend-build /frontend/dist/static/index.js /app/static/index.js

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir mysql-connector-python fastapi-cors python-multipart pymupdf

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
