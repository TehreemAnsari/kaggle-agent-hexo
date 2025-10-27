FROM python:3.11-slim

RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

# Copy requirements from the runner folder
COPY runner/requirements.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt

WORKDIR /app

# Copy local code into container
COPY agent_like/ /app/agent_like/
COPY runner/runner_main.py /app/runner_main.py

ENTRYPOINT ["python", "/app/runner_main.py"]
