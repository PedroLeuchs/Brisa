FROM python:3.12-slim
WORKDIR /srv
COPY remote/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home relay && mkdir /data && chown relay:relay /data
COPY remote/ ./remote/
USER relay
ENV BRISA_RELAY_DB=/data/relay.sqlite3
EXPOSE 8090
CMD ["uvicorn","remote.broker:create_app","--factory","--host","0.0.0.0","--port","8090","--workers","1","--no-access-log","--no-proxy-headers"]
