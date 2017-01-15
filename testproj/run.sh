#!/usr/bin/env bash
export PYTHONPATH="${PYTHONPATH}:../"
uwsgi --http-socket :8000 --master --ugreen --wsgi-file ../uwsgi_asgi.py --async 100 --mule=../reader_mule.py
#uwsgi --http-socket :8000 --master --ugreen --wsgi-file ../uwsgi_asgi.py --async 100