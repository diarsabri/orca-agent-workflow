# Starter image: standard-library Python checks. Add project dependencies to this
# trusted image before using it for application checks. Runtime network stays off.
FROM python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd
RUN apt-get update && apt-get install -y --no-install-recommends make git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home gate && mkdir /work && chown gate /work
ENV PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_INDEX=1
USER gate
WORKDIR /work
