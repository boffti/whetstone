FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a normal user: submitted code runs inside this container.
RUN useradd --create-home dojo && mkdir -p /app/my && chown -R dojo /app
USER dojo

EXPOSE 8000
CMD ["python", "-m", "whetstone", "serve", "--host", "0.0.0.0", "--port", "8000"]
