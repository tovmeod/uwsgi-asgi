import logging
import os
import six
import time
from six.moves.urllib_parse import unquote  # todo test is I actually need this or does uwsgi already parses?
import uwsgi
import umsgpack
# from asgi_redis import RedisChannelLayer
# from daphne.ws_protocol import WebSocketProtocol

__version__ = "0.1"

logger = logging.getLogger(__name__)
try:
    from testproject.asgi import channel_layer
    from testproject.wsgi import application as wsgi_app
except ImportError:
    from testproj.testproject.asgi import channel_layer
    from testproj.testproject.wsgi import application as wsgi_app

# if isinstance(channel_layer, RedisChannelLayer):  # can I check this without importing? maybe using the class name?
#     pass  # For now I support only the redis backend
# else:
#     uwsgi.stop()

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


# class WebSocket(WebSocketProtocol):
class WebSocket:
    def __init__(self, env, reply_channel, channel_layer, path, query_string, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reply_channel = reply_channel
        self.channel_layer = channel_layer
        self.path = path
        clean_headers = []
        for name, value in env.items():
            if not name.startswith('HTTP_'):
                continue
            name = name[5:]
            # name = name.encode("ascii")
            # Prevent CVE-2015-0219  ??
            if "_" in name:
                continue
            # clean_headers.append((name.lower(), value.encode("latin1")))
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
        logger.debug("WebSocket open for %s", self.reply_channel)
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
        # If we're muted, do nothing.
        # if self.muted:
        #     logger.debug("Muting incoming frame on %s", self.reply_channel)
        #     return
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
        print('finished processing message')
    except OSError:
        pass  # probably the websocket is closed


class IPC:
    def __init__(self, name, reader):
        self.name = '/tmp/{}'.format(name).replace('!', '_')
        self.name = '/home/avraham/{}'.format(name)
        self.reader = reader
        if reader:
            os.mkfifo(self.name)
            self.pipeinfd = os.open(self.name, os.O_RDONLY | os.O_NONBLOCK)
            self.pipein = os.fdopen(self.pipeinfd, 'rb')
        else:
            self.pipeinfd = None
            self.pipeoutfd = os.open(self.name, os.O_WRONLY)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if self.pipeinfd:
            os.close(self.pipeinfd)
        if self.reader and os.path.exists(self.name):
            os.remove(self.name)

    @property
    def fileno(self):
        return self.pipeinfd

    def receive_message(self):
        msgdata = self.pipein.read()
        return umsgpack.unpackb(msgdata)

    def send_message(self, message):
        msgdata = umsgpack.packb(message)
        os.write(self.pipeoutfd, msgdata)


def application(env, start_response):
    # ws_scheme = 'ws'
    # if 'HTTPS' in env or env['wsgi.url_scheme'] == 'https':
    #     ws_scheme = 'wss'

    # Get client address if possible
    # if hasattr(self.client, "host") and hasattr(self.client, "port"):
    #     self.client_addr = [self.client.host, self.client.port]
    #     self.server_addr = [self.host.host, self.host.port]
    # else:
    #     self.client_addr = None
    #     self.server_addr = None
    # Check for unicodeish path (or it'll crash when trying to parse)
    print('request id {}'.format(uwsgi.request_id()))
    try:
        path = env['PATH_INFO'].encode("ascii")  # not sure if I need to check, maybe uwsgi already does
    except UnicodeEncodeError:
        return basic_error(start_response, 400, b"Bad Request", "Invalid characters in path")
    query_string = env['QUERY_STRING']
    if 'HTTP_UPGRADE' in env and env['HTTP_UPGRADE'].lower() == "websocket":  # it means this is a ws request
        try:
            uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))
        except OSError:
            return ''  # unable to complete websocket handshake
        # Make sending channel
        reply_channel = channel_layer.new_channel("websocket.send!")
        protocol = WebSocket(env, reply_channel, channel_layer, path, query_string)
        code = protocol.onOpen()
        if code:
            return code

        websocket_fd = uwsgi.connection_fd()
        with IPC(reply_channel, reader=True) as wsipc:
            print('wsipc fd {}'.format(wsipc.fileno))
            while True:
                try:
                    uwsgi.wait_fd_read(websocket_fd, 3)
                except OSError:  # client closed the socket
                    print('websocket_fd {}'.format(websocket_fd))
                    print('client closed socket')
                    return ''
                try:
                    uwsgi.wait_fd_read(wsipc.fileno)
                except OSError as e:  # sometimes it throws 'OSError: unable to fd 16 to the event queue'
                    print('error waiting for ipc {}, reply channel {}'.format(wsipc.fileno, reply_channel))
                    print(e)
                    uwsgi.stop()
                uwsgi.suspend()
                fd = uwsgi.ready_fd()
                if fd > -1:
                    if fd == websocket_fd:
                        try:
                            msg = uwsgi.websocket_recv_nb()
                        except OSError:  # websocket closed on client side
                            return ''
                        if msg:
                            code = protocol.onMessage(msg, False)
                            if code:
                                return code
                    elif fd == wsipc.fileno:
                        msg = wsipc.receive_message()
                        uwsgi.log('got ipc message '+str(msg))
                        if msg['reply_channel'] != reply_channel:
                            print('msg reply_channel different {} {}'.format(msg['reply_channel'], reply_channel))
                            uwsgi.stop()
                        if process_message(msg):
                            return ''
                else:  # on timeout call websocket_recv_nb again to manage ping/pong
                    try:
                        msg = uwsgi.websocket_recv_nb()
                    except OSError:
                        return ''  # unable to receive websocket message
                    if msg:
                        protocol.onMessage(msg, False)
                print('.', end='', flush=True)
    else:  # normal http
        return wsgi_app(env, start_response)
