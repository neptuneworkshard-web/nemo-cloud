FROM python:3.11-slim
WORKDIR /app
COPY *.py *.yaml *.sh ./
COPY credentials.env .
RUN pip install --no-cache-dir flask yfinance requests numpy pandas
ENV PORT=8080
CMD ["python", "nemo_app.py"]
