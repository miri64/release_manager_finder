#! /bin/sh
#
# docker-entrypoint.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt -r requirements-web.txt
touch /app/opt-out
/app/web.py -o /app/opt-out -p 8888
