FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webapp/ webapp/
COPY start.py .
COPY data/factbook.db /app/data/factbook.db

ENV DB_PATH=/data/factbook.db
ENV PORT=8080

EXPOSE 8080

CMD ["python", "start.py"]
