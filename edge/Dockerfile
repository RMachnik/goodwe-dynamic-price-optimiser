FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir aiomqtt

COPY mock_agent.py .

CMD ["python", "mock_agent.py"]
