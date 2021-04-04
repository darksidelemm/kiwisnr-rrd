FROM debian:bullseye

RUN apt-get update && apt-get install -y python3-rrdtool \
    rrdtool python3-numpy python3-matplotlib python3-pip \
    && rm -rf /var/lib/apt/lists/

RUN pip3 install suntime

RUN mkdir /output
RUN mkdir /data

COPY . /app

WORKDIR /data

VOLUME "/data"
VOLUME "/output"

ENTRYPOINT [ "/app/entrypoint.sh" ]