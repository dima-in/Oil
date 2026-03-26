FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY . /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir mysql-connector-python fastapi-cors python-multipart pymupdf

# Копирование собранного frontend в static (правильный путь)
RUN cp /app/frontend/dist/static/index.css /app/static/ && \
    cp /app/frontend/dist/static/index.js /app/static/

WORKDIR /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
