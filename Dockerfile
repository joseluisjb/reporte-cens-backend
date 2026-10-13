FROM python:3.13-slim

WORKDIR /app

RUN addgroup --system app && adduser --system --group app

COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY . .

RUN chown -R app:app /app
USER app

EXPOSE 8000

ENTRYPOINT ["sh", "entrypoint.sh"]
