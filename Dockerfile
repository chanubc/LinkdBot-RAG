FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x deploy/entrypoint.sh

EXPOSE 8000

CMD ["deploy/entrypoint.sh"]
`