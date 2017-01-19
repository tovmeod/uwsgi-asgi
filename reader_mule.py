import os
import sys

import time
import umsgpack

sys.path.append(os.getcwd())
try:
    import uwsgi
    log = uwsgi.log
except ImportError:
    log = print
from uwsgi_asgi import channel_layer, get_pipe_name


class LayerWrapperWriter:
    def __init__(self):
        self._channels = {}
        # open pipe to get new channels
        self.name = get_pipe_name('reader_mule')
        if os.path.exists(self.name):
            os.remove(self.name)
        os.mkfifo(self.name)
        self.pipeinfd = os.open(self.name, os.O_RDONLY | os.O_NONBLOCK)
        self.pipein = os.fdopen(self.pipeinfd, 'rb')

    def close(self):
        os.close(self.pipeinfd)
        if os.path.exists(self.name):
            os.remove(self.name)

    def read(self):
        # uwsgi.wait_fd_read(self.pipeinfd)
        # uwsgi.suspend()
        # if self.pipeinfd == uwsgi.ready_fd():
        msgdata = self.pipein.read()
        if msgdata:
            chname = umsgpack.unpackb(msgdata)
            if chname.startswith('-'):
                print('removing channel from reader {}'.format(chname))
                chname = chname[1:]
                try:
                    fd = self._channels.pop(chname)
                    os.close(fd)
                except KeyError:
                    pass
            else:
                if chname not in self._channels:
                    self._channels[chname] = os.open(get_pipe_name(chname), os.O_WRONLY)

    def send(self, chname, message):
        msgdata = umsgpack.packb(message)
        os.write(self._channels[chname], msgdata)

    @property
    def channels(self):
        return self._channels.keys()


def reader():
    """
    todo: run this should run in a uwsgi programmed mule and send the received messages to the thread using named pipes
    pipe will be named using the reply_channel name eg '/tmp/{}'.format(reply_channel)
    """
    layer_wrapper = LayerWrapperWriter()
    while True:
        layer_wrapper.read()
        channel, message = channel_layer.receive_many(layer_wrapper.channels, block=False)
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
                # print('got message from channel layer {} {} {}'.format(type(message), channel, message))
                try:
                    layer_wrapper.send(channel, message)
                    # wsipc = ipc.get(message['reply_channel'], IPC(message['reply_channel'], reader=False))
                    # wsipc.send_message(message)
                except (ConnectionRefusedError, FileNotFoundError):
                    pass  # ws closed, ignore message
            except Exception as e:
                log("HTTP/WS send decode error: %s" % e)
                raise
        else:
            time.sleep(0.05)
    uwsgi.log('finished reader mule!!!')

if __name__ == '__main__':
    reader()
