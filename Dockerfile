FROM python:3-alpine

WORKDIR /app/

COPY . .

EXPOSE 8888

ENTRYPOINT ["./docker-entrypoint.sh"]
