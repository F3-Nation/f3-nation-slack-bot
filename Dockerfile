FROM python:3.12

ARG CACHEBUST=1
ENV PYTHONUNBUFFERED True

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

ENV GOOGLE_FUNCTION_TARGET=handler
EXPOSE 8080

CMD ["functions-framework", "--target", "handler", "--port", "8080"]