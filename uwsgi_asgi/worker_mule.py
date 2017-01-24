from channels import DEFAULT_CHANNEL_LAYER, channel_layers
from channels.signals import worker_process_ready
from channels.worker import Worker
from django.core.wsgi import get_wsgi_application

import uwsgi

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings.channels_redis")

# bootstrap application
get_wsgi_application()  # TODO: do I really need this?

channel_layer = channel_layers[DEFAULT_CHANNEL_LAYER]

worker = Worker(channel_layer=channel_layer, signal_handlers=False)


def run_worker():
    print('running worker mule')
    worker_process_ready.send(sender=worker)
    worker.ready()
    worker.run()


def finish():
    worker.sigterm_handler(None, None)

if __name__ == '__main__':
    uwsgi.atexit = finish
    run_worker()
