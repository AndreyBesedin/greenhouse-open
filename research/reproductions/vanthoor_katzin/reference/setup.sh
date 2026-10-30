#!/usr/bin/env bash
# Sets up the reference implementation apart from the repository's own
# environment: GreenLight 2.0.7 (commit d6282a1, BSD 3-Clause Clear), its
# wheel downloaded from PyPI and checked by its sha256, and a virtual
# environment of its own with what its model run imports (numpy, scipy,
# pandas, numexpr). Its metadata also asks for matplotlib and tkcalendar,
# which only its user interface imports; they are left out, the wheel
# installed without its dependencies.
#
#     research/reproductions/vanthoor_katzin/reference/setup.sh <folder>
#
# Then <folder>/venv/bin/python runs run_reference.py.
set -euo pipefail

folder="${1:?a folder to set the reference up in}"
url="https://files.pythonhosted.org/packages/5b/2d/9c599701b828536d0093e8b645936e8cfccb402f2d8fb4514f3563154b50/greenlight-2.0.7-py2.py3-none-any.whl"
wheel="greenlight-2.0.7-py2.py3-none-any.whl"
sha256="67b24ac7138cea3cc91cbba801ba1a33114ff006921f28add4313817870eaf9e"

mkdir -p "$folder"
cd "$folder"
curl -sSL -o "$wheel" "$url"
got="$(python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$wheel")"
if [ "$got" != "$sha256" ]; then
    echo "the wheel's sha256 is $got, not $sha256" >&2
    exit 1
fi
uv venv -q --python 3.12 venv
VIRTUAL_ENV="$PWD/venv" uv pip install -q --no-deps "./$wheel"
VIRTUAL_ENV="$PWD/venv" uv pip install -q numpy==2.5.4 scipy==1.18.1 pandas==3.1.0 numexpr==2.14.2
