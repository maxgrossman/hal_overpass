#!/bin/bash
set -ue

if [ ! -f venv/pyvenv.cfg ] || [ "${DO_PIP_INSTALL:-0}" = "1" ]; then
    python3 -m venv venv
    ./venv/bin/pip install -r requirements/requirements.txt
fi

./venv/bin/python src/server.py
