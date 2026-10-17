FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -m database.init_db

ENV NO_RELOAD=1
EXPOSE 8000

CMD ["python", "run.py"]
