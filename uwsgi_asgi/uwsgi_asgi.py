import importlib
import logging
import os
import time
from contextlib import ExitStack

import six
import umsgpack
from asgi_redis import RedisChannelLayer

import uwsgi

from six.moves.urllib_parse import unquote  # todo test is I actually need this or does uwsgi already parses? NOQA isort:skip

# from daphne.ws_protocol import WebSocketProtocol

logger = logging.getLogger(__name__)
try:
    # from testproject.asgi import channel_layer
    # from testproject.asgi_for_ipc import channel_layer
    from testproject.wsgi import application as wsgi_app
except ImportError:
    # from testproj.testproject.asgi import channel_layer
    # from tests.testproj.testproject import channel_layer
    from tests.testproj.testproject.wsgi import application as wsgi_app


module_path, object_path = os.environ['channel_layer'].split(":", 1)
channel_layer = importlib.import_module(module_path)
for bit in object_path.split("."):
    channel_layer = getattr(channel_layer, bit)
error_template = """
        <html>
            <head>
                <title>%(title)s</title>
                <style>
                    body { font-family: sans-serif; margin: 0; padding: 0; }
                    h1 { padding: 0.6em 0 0.2em 20px; color: #896868; margin: 0; }
                    p { padding: 0 0 0.3em 20px; margin: 0; }
                    footer { padding: 1em 0 0.3em 20px; color: #999; font-size: 80%%; font-style: italic; }
                </style>
            </head>
            <body>
                <h1>%(title)s</h1>
                <p>%(body)s</p>
                <footer>Daphne</footer>
            </body>
        </html>
    """.replace("\n", "").replace("    ", " ").replace("   ", " ").replace("  ", " ")  # Shorten it a bit, bytes wise


def basic_error(start_response, status, status_text, body):
    start_response('{} {}'.format(status, status_text), [('Content-Type', 'text/html')])
    return (error_template % {
                "title": str(status) + " " + status_text.decode("ascii"),
                "body": body,
            }).encode("utf8")


class WebSocketApp:
    def __init__(self, env, reply_channel, channel_layer, path, query_string):
        self.reply_channel = reply_channel
        self.channel_layer = channel_layer
        self.path = path
        clean_headers = []
        for name, value in env.items():
            if not name.startswith('HTTP_'):
                continue
            clean_headers.append((name.lower(), value))
        self.request_info = {
            "path": path,
            "headers": clean_headers,
            "query_string": self.unquote(query_string.encode('ascii')),
            "client": None,
            "server": None,
            "reply_channel": self.reply_channel,
            "order": 0,
        }
        self.packets_received = 0

    def onOpen(self):
        # Send news that this channel is open
        try:
            self.channel_layer.send("websocket.connect", self.request_info)
        except self.channel_layer.ChannelFull:
            # You have to consume websocket.connect according to the spec,
            # so drop the connection.
            logger.warning("WebSocket force closed for %s due to connect backpressure", self.reply_channel)
            # Send code 1013 "try again later" with close.
            # self.sendCloseFrame(code=1013, isReply=False)
            return '1013'

    def onMessage(self, payload, isBinary):
        logger.debug("WebSocket incoming frame on %s", self.reply_channel)
        self.packets_received += 1
        self.last_data = time.time()
        try:
            if isBinary:
                self.channel_layer.send("websocket.receive", {
                    "reply_channel": self.reply_channel,
                    "path": self.unquote(self.path),
                    "order": self.packets_received,
                    "bytes": payload,
                })
            else:
                self.channel_layer.send("websocket.receive", {
                    "reply_channel": self.reply_channel,
                    "path": self.unquote(self.path),
                    "order": self.packets_received,
                    "text": payload.decode("utf8"),
                })
        except self.channel_layer.ChannelFull:
            # You have to consume websocket.receive according to the spec,
            # so drop the connection.
            logger.warning("WebSocket force closed for %s due to receive backpressure", self.reply_channel)
            # Send code 1013 "try again later" with close.
            # self.sendCloseFrame(code=1013, isReply=False)
            return '1013'

    @classmethod
    def unquote(cls, value):
        """
        Python 2 and 3 compat layer for utf-8 unquoting
        """
        if six.PY2:
            return unquote(value).decode("utf8")
        else:
            return unquote(value.decode("ascii"))


def process_message(message):
    try:
        if message.get("bytes", None):
            uwsgi.websocket_send_binary(message["bytes"])
        if message.get("text", None):
            uwsgi.websocket_send(message["text"])
        if message.get("close", False):
            print('closing websocket')
            return True
    except (OSError, AttributeError):
        # OSError probably the websocket is closed
        # AttributeError probably message is None
        pass
        print('process_message exception {}'.format(message), end='', flush=True)


class LayerEpollWrapper:
    def connect(self, channel_name, ch_layer):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    @property
    def fileno(self):
        raise NotImplementedError

    def receive(self):
        raise NotImplementedError

    def __del__(self):
        print('delete')
        self.close()


def get_pipe_name(channel_name):
    # return '/tmp/{}'.format(channel_name)
    return '/home/avraham/{}'.format(channel_name)


class GenericLayerWrapper(LayerEpollWrapper):
    pipeinfd = None
    channel_name = None
    reader_mule_pipe = None

    def connect(self, channel_name, ch_layer):
        self.channel_name = channel_name
        self._pipe_name(channel_name)
        os.mkfifo(self.name)
        self.pipeinfd = os.open(self.name, os.O_RDONLY | os.O_NONBLOCK)
        self.pipein = os.fdopen(self.pipeinfd, 'rb')

        try:
            self.reader_mule_pipe = self.pipeoutfd = os.open(get_pipe_name('reader_mule'), os.O_WRONLY)
        except FileNotFoundError:
            uwsgi.log('You must run a reader mule if using a channel layer without the epoll extension')
            return False
        # notify reader to listen to a new channel
        namedata = umsgpack.packb(channel_name)
        os.write(self.reader_mule_pipe, namedata)
        return True

    def open_writer(self, channel_name):
        self._pipe_name(channel_name)
        self.pipeoutfd = os.open(self.name, os.O_WRONLY)

    def _pipe_name(self, channel_name):
        self.name = '/tmp/{}'.format(channel_name)
        self.name = '/home/avraham/{}'.format(channel_name)

    def close(self):
        print('closing LayerWrapper')
        if self.pipeinfd:
            os.close(self.pipeinfd)
            self.pipeinfd = None
            if os.path.exists(self.name):
                os.remove(self.name)
        # notify reader to not listen to this channel anymore
        if self.reader_mule_pipe:
            if self.channel_name:
                namedata = umsgpack.packb('-{}'.format(self.channel_name))
                os.write(self.reader_mule_pipe, namedata)
            os.close(self.reader_mule_pipe)
            self.reader_mule_pipe = None

    @property
    def fileno(self):
        return self.pipeinfd

    def receive(self):
        msgdata = self.pipein.read()
        if msgdata:
            return umsgpack.unpackb(msgdata)
        return None

    def send(self, message):
        msgdata = umsgpack.packb(message)
        os.write(self.pipeoutfd, msgdata)


class RedisLayerWrapper(LayerEpollWrapper):
    def receive(self):
        msg = self._receive()
        self._ask()
        return msg

    def _receive(self):
        result = self.redis_client.parse_response(self.redis_conn, 'BLPOP')
        if result is None:
            return None
        content = self.redis_client.get(result[1])
        if content is None:
            return None
        return self.channel_layer.deserialize(content)

    def _ask(self, timeout=0):
        self.redis_conn.send_command('BLPOP', 'asgi:' + self.channel_name, timeout)

    def connect(self, channel_name, ch_layer):
        self.channel_name = channel_name
        self.channel_layer = ch_layer
        self.redis_client = self.channel_layer.connection(None)
        self.redis_conn = self.redis_client.connection_pool.get_connection('')
        # self.redis_conn.connect()
        self.redis_fd = self.redis_conn._sock.fileno()
        self._ask(3)
        return True

    def close(self):
        self.redis_conn.disconnect()

    @property
    def fileno(self):
        return self.redis_fd


def get_layer_wrapper():
    # if isinstance(ch_layer, LayerEpollWrapper):
    #     return GenericLayerWrapper()
    if isinstance(channel_layer, RedisChannelLayer):
        return RedisLayerWrapper()
    return None


def application(env, start_response):
    # Get client address if possible
    # if hasattr(self.client, "host") and hasattr(self.client, "port"):
    #     self.client_addr = [self.client.host, self.client.port]
    #     self.server_addr = [self.host.host, self.host.port]
    # else:
    #     self.client_addr = None
    #     self.server_addr = None
    # Check for unicodeish path (or it'll crash when trying to parse)
    try:
        path = env['PATH_INFO'].encode("ascii")  # not sure if I need to check, maybe uwsgi already does
    except UnicodeEncodeError:
        return basic_error(start_response, 400, b"Bad Request", "Invalid characters in path")
    query_string = env['QUERY_STRING']
    if 'HTTP_UPGRADE' in env and env['HTTP_UPGRADE'].lower() == "websocket":  # it means this is a ws request
        with ExitStack() as stack:
            # Make sending channel
            reply_channel = channel_layer.new_channel("websocket.send!")
            wsapp = WebSocketApp(env, reply_channel, channel_layer, path, query_string)
            code = wsapp.onOpen()  # send to channel layer the connect message and wait for 'accept': True
            if code:
                return code
            layer_wrapper = get_layer_wrapper()
            # stack.callback(epoll_layer.close)
            # assert isinstance(epoll_layer, LayerEpollMixin)
            if layer_wrapper and not layer_wrapper.connect(reply_channel, channel_layer):
                return basic_error(start_response, 500, b"Denied", "Could not connect to channel layer")

            # wait for response before sending handshake
            received_msg = None
            if layer_wrapper:
                print('epoll layer {}'.format(type(layer_wrapper)))
                uwsgi.wait_fd_read(layer_wrapper.fileno)
                uwsgi.suspend()
                fd = uwsgi.ready_fd()
                if fd == layer_wrapper.fileno:
                    received_msg = layer_wrapper.receive()
            else:
                print('not epoll layer')
                start = time.time()
                while time.time() - start < 3:
                    ch, received_msg = channel_layer.receive([reply_channel], block=False)
                    if ch:
                        break
            if received_msg != {'accept': True}:
                print('timeout or accept is not true')
                return basic_error(start_response, 403, b"Denied", "Websocket connection refused by the application")
            else:
                try:
                    uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))
                except OSError:
                    return ''  # unable to complete websocket handshake

            websocket_fd = uwsgi.connection_fd()
            if layer_wrapper:
                websocket_fd_timeout = 3
            else:
                websocket_fd_timeout = 1
                ppcounter = time.time()  # if not epolling channel layer count the time to send ping/pong
            while True:
                try:
                    uwsgi.wait_fd_read(websocket_fd, websocket_fd_timeout)
                except OSError:  # client closed the socket
                    print('websocket_fd {}'.format(websocket_fd))
                    print('aeae client closed socket')
                    return ''

                if layer_wrapper:
                    uwsgi.wait_fd_read(layer_wrapper.fileno)

                uwsgi.suspend()
                fd = uwsgi.ready_fd()
                if fd == websocket_fd:
                    try:
                        msg = uwsgi.websocket_recv_nb()
                    except OSError:  # websocket closed on client side
                        print('websocket closed on client side when trying to read {}'.format(reply_channel))
                        return ''
                    if msg:
                        code = wsapp.onMessage(msg, False)
                        if code:
                            print('onMessage code {}'.format(code))
                            return code
                elif layer_wrapper and fd == layer_wrapper.fileno:
                    msg = layer_wrapper.receive()
                    if process_message(msg):
                        return ''
                else:  # on timeout call websocket_recv_nb again to manage ping/pong, typically on this point fd == -1
                    if layer_wrapper or (not layer_wrapper and time.time() - ppcounter > 3):
                        print('ping/pong ', end='', flush=True)
                        try:
                            msg = uwsgi.websocket_recv_nb()
                            if not layer_wrapper:
                                ppcounter = time.time()
                        except OSError:
                            print('unable to receive websocket message')
                            return ''  # unable to receive websocket message
                        if msg:
                            wsapp.onMessage(msg, False)
                    if not layer_wrapper:
                        ch, msg = channel_layer.receive([reply_channel], block=False)
                        if ch:
                            if process_message(msg):
                                return ''
                print('.', end='', flush=True)
    else:  # normal http
        return wsgi_app(env, start_response)
