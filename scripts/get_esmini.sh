#!/usr/bin/env bash
# Download the esmini OpenSCENARIO player (Linux x86-64) into ./esmini
set -euo pipefail
VERSION=${ESMINI_VERSION:-v3.10.2}
curl -sSL -o esmini.zip "https://github.com/esmini/esmini/releases/download/${VERSION}/esmini-bin_Linux.zip"
unzip -q -o esmini.zip && rm esmini.zip
./esmini/bin/esmini --version | head -2
