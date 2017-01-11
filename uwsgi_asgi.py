import json
import logging
import uwsgi
import redis
import msgpack
from asgi_redis import RedisChannelLayer
from daphne.ws_protocol import WebSocketProtocol

__version__ = "0.1"

logger = logging.getLogger(__name__)
try:
    from testproject.asgi import channel_layer
    from testproject.wsgi import application as wsgi_app
except ImportError:
    from testproject.testproject.asgi import channel_layer
    from testproject.testproject.wsgi import application as wsgi_app

if isinstance(channel_layer, RedisChannelLayer):  # can I check this without importing? maybe using the class name?
    pass  # For now I support only the redis backend
else:
    uwsgi.stop()

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


class WebSocket(WebSocketProtocol):
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
            self.muted = True
            logger.warning("WebSocket force closed for %s due to connect backpressure", self.reply_channel)
            # Send code 1013 "try again later" with close.
            self.sendCloseFrame(code=1013, isReply=False)


def backend_reader_sync(redis_server, channel_layer, reply_channel, protocol):
    """
    Runs as an-often-as-possible task with the reactor, unless there was
    no result previously in which case we add a small delay.
    """
    channels = ['websocket.receive']
    delay = 0.05
    # Don't do anything if there's no channels to listen on
    if channels:
        delay = 0.01
        channel, message = channel_layer.receive(channels, block=False)
        if channel:
            delay = 0.00
            # Deal with the message
            try:
                # unknown_message_keys = set(message.keys()) - {"bytes", "text", "close"}
                # if unknown_message_keys:
                #     raise ValueError(
                #         "Got invalid WebSocket reply message on %s - contains unknown keys %s" % (
                #             channel,
                #             unknown_message_keys,
                #         )
                #     )
                # print('got message from channel layer {} {} {}'.format(type(message), channel, message))
                if reply_channel != message['reply_channel']:
                    print('sending back to redis {}'.format(message))
                    send_to_channel(redis_server, message['reply_channel'][15:], message)
                else:
                    # print('got message from the same thread {}'.format(reply_channel))
                    return process_message(message)
                # if message.get("bytes", None):
                #     uwsgi.websocket_send_binary(message["bytes"])
                # if message.get("text", None):
                #     uwsgi.websocket_send(message["text"])
                # if message.get("close", False):
                #     return True
            except Exception as e:
                logger.error("HTTP/WS send decode error: %s" % e)
    # reactor.callLater(delay, self.backend_reader_sync)


def send_to_channel(redis_server, sub_name, message):
    print(redis_server.publish('alo', 'message text'))
    message['alo'] = 'aloo'
    print(msgpack.packb(message))
    print(redis_server.publish('alo', msgpack.packb(message)))
    print(redis_server.publish('listen'+sub_name, msgpack.packb(message)))


def process_message(message):
    if message.get("bytes", None):
        uwsgi.websocket_send_binary(message["bytes"])
    if message.get("text", None):
        uwsgi.websocket_send(message["text"])
    if message.get("close", False):
        print('closing websocket')
        return True


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
    try:
        path = env['PATH_INFO'].encode("ascii")  # not sure if I need to check, maybe uwsgi already does
    except UnicodeEncodeError:
        return basic_error(start_response, 400, b"Bad Request", "Invalid characters in path")
    query_string = env['QUERY_STRING']
    if 'HTTP_UPGRADE' in env and env['HTTP_UPGRADE'].lower() == "websocket":  # it means this is a ws request
        uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))
        # print("websockets...")
        # Make sending channel
        reply_channel = channel_layer.new_channel("websocket.send!")
        sub_name = 'listen'+reply_channel[15:]
        protocol = WebSocket(env, reply_channel, channel_layer, path, query_string)
        protocol.onOpen()

        redis_server = redis.StrictRedis(host='localhost', port=6379, db=0)
        redis_server.publish('alo', 'opened ws')
        redis_fd = None
        websocket_fd = uwsgi.connection_fd()

        while True:
            # print('trying to get redis fd')
            # redis_conn = channel_layer.lpopmany.registered_client.connection_pool.get_connection('')
            # if redis_conn._sock:
            #     redis_fd = redis_conn._sock.fileno()
            # else:
            #     redis_fd = None
            if redis_fd is None and False:
                channel = redis_server.pubsub()
                channel.subscribe(sub_name)
                redis_server.publish('alo', 'redis_fd was None')
                redis_fd = channel.connection._sock.fileno()
            # print('redis fd {} reply channel {}'.format(redis_fd, reply_channel))
            # redis_fd = None

            try:
                uwsgi.wait_fd_read(websocket_fd, 3)
            except OSError:  # client closed the socket
                print('websocket_fd {}'.format(websocket_fd))
                print('client closed socket')
                return ''
            try:
                if redis_fd:
                    uwsgi.wait_fd_read(redis_fd)
            except OSError as e:  # I don't know why, sometimes it throws 'OSError: unable to fd 16 to the event queue'
                print(e)
                redis_fd = None
                channel.connection.disconnect()
            uwsgi.suspend()
            fd = uwsgi.ready_fd()
            if fd > -1:
                if fd == websocket_fd:
                    try:
                        msg = uwsgi.websocket_recv_nb()
                    except OSError:  # websocket closed on client side
                        return ''
                    if msg:
                        # r.publish('foobar', msg)
                        protocol.onMessage(msg, False)
                elif redis_fd and fd == redis_fd:
                    print('Redis FD {} ready reply channel {}'.format(redis_fd, reply_channel))
                    t, ch, message = channel.parse_response()
                    print(t, ch, message)
                    if t == b'message':
                        message = message.decode('utf-8')
                        print(type(message))
                        print(message)
                        message = json.loads(message)
                        print(type(message))
                        print(message)
                        # uwsgi.websocket_send("[%s] %s" % (time.time(), msg))
                        if process_message(message):
                            return ''
            else:
                # on timeout call websocket_recv_nb again to manage ping/pong
                msg = uwsgi.websocket_recv_nb()
                if msg:
                    protocol.onMessage(msg, False)
            if backend_reader_sync(redis_server, protocol.channel_layer, protocol.reply_channel, protocol):
                return ''
            print('.', end='', flush=True)
    else:  # normal http
        return wsgi_app(env, start_response)
