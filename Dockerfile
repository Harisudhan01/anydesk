FROM python:3.11-slim
WORKDIR /app
COPY config.py network_protocol.py relay_server.py ./
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "relay_server.py"]
