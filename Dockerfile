FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 APP_HOME=/app GOOGLE_FUNCTION_TARGET=handler
WORKDIR $APP_HOME

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
EXPOSE 8080
CMD ["functions-framework", "--target", "handler", "--port", "8080"]