FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY . /app

RUN pip install --upgrade pip && \
    pip install mysql-connector-python

CMD ["bash"]

