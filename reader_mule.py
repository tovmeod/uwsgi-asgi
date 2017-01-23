import os
import sys
import time

import umsgpack

from uwsgi_asgi import channel_layer, get_pipe_name

sys.path.append(os.getcwd())
try:
    import uwsgi
    log = uwsgi.log
except ImportError:
    log = print


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
                print('removing channel from reader {} {}'.format(chname, len(self.channels)))
                chname = chname[1:]
                try:
                    fd = self._channels.pop(chname)
                    os.close(fd)
                except KeyError:
                    pass
            else:
                self.remove(chname)

    def send(self, chname, message):
        msgdata = umsgpack.packb(message)
        try:
            os.write(self._channels[chname], msgdata)
        except BrokenPipeError:
            self.remove(chname)

    def remove(self, chname):
        if chname not in self._channels:
            if not os.path.exists(get_pipe_name(chname)):
                print('pipe does not exists!! {}'.format(get_pipe_name(chname)))
            self._channels[chname] = os.open(get_pipe_name(chname), os.O_WRONLY)
            print('new channel {} {}'.format(chname, len(self.channels)))
        else:
            print('got channel name already in dict {}'.format(chname))

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
        channel, message = channel_layer.receive(layer_wrapper.channels, block=False)
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
            # print(len(layer_wrapper.channels), end='', flush=True)
            time.sleep(0.05)
    uwsgi.log('finished reader mule!!!')

if __name__ == '__main__':
    reader()
