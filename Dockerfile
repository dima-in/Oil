FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY . /app

RUN pip install --upgrade pip && \
    pip install mysql-connector-python fastapi-cors python-multipart

CMD ["bash"]
