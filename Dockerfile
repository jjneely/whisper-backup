FROM ubuntu:16.04

ENV VERSION 0.1.2

ENV BOTO_VERSION 2.46.1
ENV CARBON_VERSION 0.9.15
ENV GRAPHITE_VERSION 0.9.15

RUN apt-get update && \
    apt-get -y install python2.7 python-pip wget unzip && \
    wget -O /opt/whisper-backup-"$VERSION".zip https://github.com/jjneely/whisper-backup/releases/download/"$VERSION"/whisper-backup-"$VERSION".zip && \
    cd /opt/ && \
    unzip -d whisper-backup whisper-backup-"$VERSION".zip && \
    rm whisper-backup-"$VERSION".zip && \
    apt-get purge -y wget unzip

RUN pip install boto==2.38.0 && \
    pip install carbon==$CARBON_VERSION && \
    pip install graphite-web==$GRAPHITE_VERSION && \
    pip install whisper==$GRAPHITE_VERSION

RUN cd /opt/whisper-backup && python setup.py install

WORKDIR /opt/whisper-backup/whisperbackup

ENTRYPOINT ["python", "whisperbackup.py"]
