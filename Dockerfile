FROM ubuntu:20.04
RUN apt-get update && apt-get install -q -y \
    git \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir -U dco-check
