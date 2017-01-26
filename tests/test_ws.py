# coding: utf8
from __future__ import unicode_literals

import time
from unittest import TestCase

import pytest
import websocket


try:
    from asgi_rabbitmq import RabbitmqChannelLayer as channel_layer_cls
    channel_layer_kwargs = {}
    asgi_file = 'testproject.asgi_for_rabbit'
except ImportError:
    try:
        from asgi_redis import RedisChannelLayer as channel_layer_cls
        channel_layer_kwargs = {}
        asgi_file = 'testproject.asgi'
    except ImportError:
        from asgi_ipc import IPCChannelLayer as channel_layer_cls
        channel_layer_kwargs = {'capacity': 100}
        asgi_file = 'testproject.asgi_for_ipc'


from tests.testproj.benchmark import Benchmarker
from uwsgi_asgi.cli import CommandLineInterface


class TestWebSocketProtocol(TestCase):
    """
    Tests that the WS protocol class correctly generates and parses messages.
    """


    @pytest.fixture(autouse=True)
    def setup_channel_layer(self, rabbitmq_url):

        if asgi_file == 'testproject.asgi_for_rabbit':
            self.channel_layer = channel_layer_cls(rabbitmq_url, **channel_layer_kwargs)
        else:
            self.channel_layer = channel_layer_cls(**channel_layer_kwargs)

    def setUp(self):
        self.server = CommandLineInterface()
        self.server.run([asgi_file, '--chdir', 'tests/testproj', '-L'], blocking=False)  # -L means disable request logging
        if 'flush' in self.channel_layer.extensions:
            self.channel_layer.flush()
        time.sleep(1)  # give some time to uwsgi to boot
        self.ws = websocket.WebSocket()

    def tearDown(self):
        self.server.close()

    @pytest.mark.timeout(10)
    def test_basic(self):
        # Send a simple request to the protocol
        self.ws.connect("ws://127.0.0.1:8000/chat", timeout=50, host='Host: somewhere.com',
                        origin='http://example.com',
                        header=["User-Agent: MyProgram", 'x-custom: header',
                                'Sec-WebSocket-Protocol: chat, superchat',
                                'header_with_underscore: value_with_underscore'])
        # _, message = self.channel_layer.receive(["websocket.connect"], block=True)
        # self.assertEqual(message['path'], b"/chat")
        # self.assertEqual(message['query_string'], "")
        # headers = dict(message['headers'])
        # self.assertIn('http_sec_websocket_key', headers)
        # headers.pop('http_sec_websocket_key')
        # self.assertEqual(headers,
        #                  {
        #                      'http_connection': 'Upgrade',
        #                      'http_header_with_underscore': 'value_with_underscore',
        #                      'http_host': 'Host: somewhere.com',
        #                      'http_origin': 'http://example.com',
        #                      'http_sec_websocket_protocol': 'chat, superchat',
        #                      'http_sec_websocket_version': '13',
        #                      'http_upgrade': 'websocket',
        #                      'http_user_agent': 'MyProgram',
        #                      'http_x_custom': 'header'
        #                  }
        # )
        # self.assertTrue(message['reply_channel'].startswith("websocket.send!"))
        # Accept the connection
        # self.channel_layer.send(message['reply_channel'], {'accept': True})

        self.ws.send('give reply channel')
        reply_channel = self.ws.recv()
        # Send some text
        print('sending on reply channel {}'.format(reply_channel))

        self.channel_layer.send(
            reply_channel,
            {'text': "Hello World!"}
        )

        response = self.ws.recv()
        self.assertEqual(response, 'Hello World!')

        # Send some bytes
        self.channel_layer.send(
            reply_channel,
            {'bytes': b"\xaa\xbb\xcc\xdd"}
        )


        opcode, data = self.ws.recv_data()
        self.assertEqual(data, b"\xaa\xbb\xcc\xdd")

        # Close the connection
        print('sending close')
        self.channel_layer.send(
            reply_channel,
            {'close': True}
        )

        with self.assertRaises(websocket.WebSocketConnectionClosedException):
            self.ws.recv_data()

    def test_openclose(self):
        self.ws.connect('ws://127.0.0.1:8000')
        self.ws.send_close()

    @pytest.mark.skipif(asgi_file == 'testproject.asgi_for_ipc', reason='IPC is buggy')
    def test_benchmark(self):
        from twisted.internet import reactor
        benchmarker = Benchmarker(
            url='ws://127.0.0.1:8000',
            num=100,
            concurrency=10,
            rate=1,
            messages=5,
            spawn=30,
            reactor=reactor
        )
        benchmarker.loop()
        reactor.run()
        self.assertEqual(benchmarker.num_good, 100)
