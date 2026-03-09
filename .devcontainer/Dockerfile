FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Install packages
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
    apt-get -y install --no-install-recommends \
    sudo
