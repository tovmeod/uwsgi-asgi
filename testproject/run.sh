#!/usr/bin/env bash
uwsgi --http-socket :8000 --master --ugreen --wsgi-file ../uwsgi_asgi.py --async 100