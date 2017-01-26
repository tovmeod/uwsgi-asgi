# Settings for channels specifically
from testproject.settings.base import *

INSTALLED_APPS += (
    'channels',
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "asgi_rabbitmq.RabbitmqChannelLayer",
        "ROUTING": "testproject.urls.channel_routing",
        "CONFIG": {
            'url': 'amqp://guest:guest@127.0.0.1:5672/%2F',
        }
    },
}
