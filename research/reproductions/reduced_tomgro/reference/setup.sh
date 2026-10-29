#!/usr/bin/env bash
# Sets up the reference implementation apart from the repository's own
# environment: Oliveira et al.'s data-assimilation-tomato-models, release
# v0.4.0 (commit b9b2c80, doi:10.5281/zenodo.13294322, MIT), checked by its
# Zenodo md5, unpacked, and a virtual environment of its own with what its
# model imports (numpy, pandas, and OpenCV, which its auxiliary module
# imports at the top).
#
#     research/reproductions/reduced_tomgro/reference/setup.sh <folder>
set -euo pipefail

folder="${1:?a folder to set the reference up in}"
url="https://zenodo.org/api/records/13294322/files/mnqoliveira/data-assimilation-tomato-models-v0.4.0.zip/content"
md5="43302bcf319dba522f84d80e9b4280a5"

mkdir -p "$folder"
cd "$folder"
curl -sSL -o reference.zip "$url"
got="$(python3 -c 'import hashlib, sys; print(hashlib.md5(open(sys.argv[1], "rb").read()).hexdigest())' reference.zip)"
if [ "$got" != "$md5" ]; then
    echo "the archive's md5 is $got, not $md5" >&2
    exit 1
fi
rm -rf src
python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall("src")' reference.zip
uv venv -q --python 3.12 venv
VIRTUAL_ENV="$PWD/venv" uv pip install -q numpy==2.5.4 pandas==3.1.0 opencv-python-headless==5.0.0
echo "$PWD/src/mnqoliveira-data-assimilation-tomato-models-b9b2c80"
