# coding: utf8
from __future__ import unicode_literals

import os
import time
from unittest import TestCase

import pytest
import websocket
from asgi_redis import RedisChannelLayer

from tests.testproj.benchmark import Benchmarker
from uwsgi_asgi.cli import CommandLineInterface


class TestWebSocketProtocol(TestCase):
    """
    Tests that the WS protocol class correctly generates and parses messages.
    """

    def setUp(self):
        self.wascwd = os.getcwd()
        os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testproj'))
        self.server = CommandLineInterface()
        self.server.run(['testproject.asgi'], blocking=False)
        self.channel_layer = RedisChannelLayer()
        self.channel_layer.connection(None).flushall()
        time.sleep(1)
        self.ws = websocket.WebSocket()

    def tearDown(self):
        self.server.close()
        os.chdir(self.wascwd)

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
