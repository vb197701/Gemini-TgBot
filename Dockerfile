FROM python:3.14.0-slim-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/ .

ENV TELEGRAM_BOT_API_KEY=""
ENV GEMINI_API_KEYS=""
ENV ADMIN_USER_IDS=""

CMD ["python", "-u", "main.py"]
