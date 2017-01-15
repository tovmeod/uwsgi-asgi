# uwsgi-asgi

Alternative to daphne, the goal is to enable django channels on uWSGI

This is alpha software, contributions are welcomed please report bugs, create PR, tests

It is included a test project
to run the websocket benchmark 'python benchmark.py ws://127.0.0.1:8000'
to run the http loadtest 'loadtest -c 10 -t 10 http://127.0.0.1:8000'

TODO:
Test the protocol specification
Multi client tests
Make a more complex testproject