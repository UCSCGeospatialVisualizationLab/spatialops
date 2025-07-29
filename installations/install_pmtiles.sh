#!/bin/bash

# Install all required packages
apt-get update && apt-get clean
apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libsqlite3-dev \
    zlib1g-dev \
    gcc \
    g++
rm -rf /var/lib/apt/lists/*

# Create and move to temporary directory
cd /tmp

# Clone and build tippecanoe (using version 2.74.0)
git clone https://github.com/felt/tippecanoe.git
cd tippecanoe
git checkout 10f7f0a
make -j
make install
cd ..
rm -rf tippecanoe
