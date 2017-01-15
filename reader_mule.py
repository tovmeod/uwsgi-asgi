import os
import sys
sys.path.append(os.getcwd())
try:
    import uwsgi
    log = uwsgi.log
except ImportError:
    log = print
from uwsgi_asgi import channel_layer, IPC


def reader():
    """
    todo: run this should run in a uwsgi programmed mule and send the received messages to the thread using named pipes
    pipe will be named using the reply_channel name eg '/tmp/{}'.format(reply_channel)
    """
    channels = ['websocket.receive']
    ipc = {}
    while True:
        channel, message = channel_layer.receive_many(channels, block=True)
        if channel:
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
                print('got message from channel layer {} {} {}'.format(type(message), channel, message))
                try:
                    wsipc = ipc.get(message['reply_channel'], IPC(message['reply_channel'], reader=False))
                    wsipc.send_message(message)
                except (ConnectionRefusedError, FileNotFoundError):
                    pass  # ws closed, ignore message
            except Exception as e:
                log("HTTP/WS send decode error: %s" % e)
                raise
    uwsgi.log('finished reader mule!!!')

if __name__ == '__main__':
    reader()
