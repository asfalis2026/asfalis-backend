
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install psycopg2-binary
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--log-level", "info", "--access-logfile", "-", "-w", "1", "--threads", "4", "--bind", "0.0.0.0:5000", "wsgi:app"]
