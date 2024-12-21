#!/bin/bash
service nginx start
python server.py
exec "$@"