FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 APP_HOME=/app GOOGLE_FUNCTION_TARGET=handler
WORKDIR $APP_HOME

COPY requirements-app.txt ./requirements-app.txt
RUN pip install --no-cache-dir -r requirements-app.txt

COPY . ./
EXPOSE 8080
CMD ["functions-framework", "--target", "handler", "--port", "8080"]