FROM python@sha256:c2aca8207dfb68e7d20fecb7fad7e145c5d79d2ff36712d416c144130606d71d
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::https::CaInfo=/etc/ssl/certs/ca-certificates.crt -o APT::Update::Error-Mode=any update \
    && apt-get -o Acquire::https::CaInfo=/etc/ssl/certs/ca-certificates.crt install -y --no-install-recommends gcc g++ default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*
USER 65534:65534
WORKDIR /tmp
