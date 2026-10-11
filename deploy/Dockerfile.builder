# Development builder only: no retail game code or assets are added to this image.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates git curl wget python3 python3-venv python3-pip \
    cmake ninja-build build-essential clang make pkg-config \
    libssl-dev zlib1g-dev libegl-dev libgles-dev \
    unzip zip xz-utils gzip rsync file \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /project
CMD ["bash"]
