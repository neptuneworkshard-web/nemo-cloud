FROM python:3.11-slim

WORKDIR /app

COPY nemo_engine.py nemo_app.py nemo_mailer.py nemo_news.py nemo_env.py .
COPY nemo_morning_update.py nemo_first_signal.py nemo_continuous_scan.py .
COPY credentials.env .

RUN pip install --no-cache-dir flask yfinance requests numpy pandas

ENV PORT=8080

CMD ["python", "nemo_app.py"]
