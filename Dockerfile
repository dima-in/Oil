FROM dockerhub.timeweb.cloud/library/node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM dockerhub.timeweb.cloud/tiangolo/uvicorn-gunicorn-fastapi:python3.9

WORKDIR /app

COPY . /app
# Весь каталог сборки: если Vite разобьёт бандл на чанки, они тоже попадут в образ.
COPY --from=frontend-build /frontend/dist/static/ /app/static/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir requests mysql-connector-python fastapi-cors python-multipart pymupdf openpyxl

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
