FROM python@sha256:c2aca8207dfb68e7d20fecb7fad7e145c5d79d2ff36712d416c144130606d71d
RUN --mount=type=secret,id=am_ca_bundle,required=false,mode=0444 \
    am_ca_file=/etc/ssl/certs/ca-certificates.crt; \
    if [ -f /run/secrets/am_ca_bundle ]; then am_ca_file=/run/secrets/am_ca_bundle; fi; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::https::CaInfo="$am_ca_file" -o APT::Update::Error-Mode=any update \
    && apt-get -o Acquire::https::CaInfo="$am_ca_file" install -y --no-install-recommends gcc g++ default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*
USER 65534:65534
WORKDIR /tmp
