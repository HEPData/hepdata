FROM ubuntu:latest

RUN apt-get update \
&& apt-get install -y gnupg wget rclone postgresql-common \
&& /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
&& apt-get update \
&& apt-get install -y postgresql-client-16 \
&& apt-get clean
