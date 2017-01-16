# coding: utf8
from __future__ import unicode_literals

from unittest import TestCase
import pytest
from asgi_redis import RedisChannelLayer
import websocket


class TestWebSocketProtocol(TestCase):
    """
    Tests that the WS protocol class correctly generates and parses messages.
    """

    def setUp(self):
        self.ws = websocket.WebSocket()
        self.channel_layer = RedisChannelLayer()
        self.channel_layer.connection(None).flushall()

    # def tearDown(self):
    #     self.channel_layer.connection(None).flushall()

    @pytest.mark.timeout(10)
    def test_basic(self):
        # Send a simple request to the protocol
        self.ws.connect("ws://127.0.0.1:8000/chat", timeout=50, host='Host: somewhere.com',
                        origin='http://example.com',
                        header=["User-Agent: MyProgram", 'x-custom: header',
                                'Sec-WebSocket-Protocol: chat, superchat',
                                'header_with_underscore: value_with_underscore'])
        _, message = self.channel_layer.receive(["websocket.connect"], block=True)
        self.assertEqual(message['path'], b"/chat")
        self.assertEqual(message['query_string'], "")
        headers = dict(message['headers'])
        self.assertIn('http_sec_websocket_key', headers)
        headers.pop('http_sec_websocket_key')
        self.assertEqual(headers,
                         {
                             'http_connection': 'Upgrade',
                             'http_header_with_underscore': 'value_with_underscore',
                             'http_host': 'Host: somewhere.com',
                             'http_origin': 'http://example.com',
                             'http_sec_websocket_protocol': 'chat, superchat',
                             'http_sec_websocket_version': '13',
                             'http_upgrade': 'websocket',
                             'http_user_agent': 'MyProgram',
                             'http_x_custom': 'header'
                         }
        )
        self.assertTrue(message['reply_channel'].startswith("websocket.send!"))
        # Accept the connection
        self.channel_layer.send(message['reply_channel'], {'accept': True})

        # Send some text
        print('sending on reply channel {}'.format(message['reply_channel']))

        self.channel_layer.send(
            message['reply_channel'],
            {'text': "Hello World!"}
        )

        response = self.ws.recv()
        self.assertEqual(response, 'Hello World!')

        # Send some bytes
        self.channel_layer.send(
            message['reply_channel'],
            {'bytes': b"\xaa\xbb\xcc\xdd"}
        )


        opcode, data = self.ws.recv_data()
        self.assertEqual(data, b"\xaa\xbb\xcc\xdd")

        # Close the connection
        print('sending close')
        self.channel_layer.send(
            message['reply_channel'],
            {'close': True}
        )

        with self.assertRaises(websocket.WebSocketConnectionClosedException):
            self.ws.recv_data()

    def test_openclose(self):
        self.ws.connect('ws://127.0.0.1:8000')
        self.ws.send_close()
