#!/usr/bin/env python
import os
import sys
import argparse
import logging
import importlib

import subprocess

# from .server import Server, build_endpoint_description_strings
# from .access import AccessLogGenerator
from _signal import SIGINT

import time
from importlib._bootstrap_external import SourceFileLoader

logger = logging.getLogger(__name__)

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8000


class CommandLineInterface(object):
    """
    Acts as the main CLI entry point for running the server.
    """

    description = "uWSGI ASGI protocol server"

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=self.description,
        )
        self.parser.add_argument(
            '-p',
            '--port',
            type=int,
            help='Port number to listen on',
            default=8000,
        )
        self.parser.add_argument(
            '--async',
            type=int,
            help='How many async cores per process',
            default=100,
        )
        self.parser.add_argument(
            'channel_layer',
            help='The ASGI channel layer instance to use as path.to.module:instance.path',
        )
        self.parser.add_argument(
            '--chdir',
            help='This is complete path of the directory to be changed to a new location, typically the django project root',
            default=None
        )
        self.parser.add_argument(
            '--uwsgipath',
            help='This is complete path of the directory to be changed to a new location, typically the django project root',
            default=os.path.join(os.path.dirname(sys.executable), 'uwsgi')
        )
        self.parser.add_argument(
            '--asgi-workers',
            type=int,
            help='Set the number of channels workers to run, set to 0 to disable.',
            default=1
        )
        # self.parser.add_argument(
        #     '-b',
        #     '--bind',
        #     dest='host',
        #     help='The host/address to bind to',
        #     default=None,
        # )
        # self.parser.add_argument(
        #     '-u',
        #     '--unix-socket',
        #     dest='unix_socket',
        #     help='Bind to a UNIX socket rather than a TCP host/port',
        #     default=None,
        # )
        # self.parser.add_argument(
        #     '--fd',
        #     type=int,
        #     dest='file_descriptor',
        #     help='Bind to a file descriptor rather than a TCP host/port or named unix socket',
        #     default=None,
        # )
        # self.parser.add_argument(
        #     '-e',
        #     '--endpoint',
        #     dest='socket_strings',
        #     action='append',
        #     help='Use raw server strings passed directly to twisted',
        #     default=[],
        # )
        # self.parser.add_argument(
        #     '-v',
        #     '--verbosity',
        #     type=int,
        #     help='How verbose to make the output',
        #     default=1,
        # )
        # self.parser.add_argument(
        #     '-t',
        #     '--http-timeout',
        #     type=int,
        #     help='How long to wait for worker server before timing out HTTP connections',
        #     default=120,
        # )
        # self.parser.add_argument(
        #     '--access-log',
        #     help='Where to write the access log (- for stdout, the default for verbosity=1)',
        #     default=None,
        # )
        # self.parser.add_argument(
        #     '--ping-interval',
        #     type=int,
        #     help='The number of seconds a WebSocket must be idle before a keepalive ping is sent',
        #     default=20,
        # )
        # self.parser.add_argument(
        #     '--ping-timeout',
        #     type=int,
        #     help='The number of seconds before a WeSocket is closed if no response to a keepalive ping',
        #     default=30,
        # )
        # self.parser.add_argument(
        #     '--ws-protocol',
        #     nargs='*',
        #     dest='ws_protocols',
        #     help='The WebSocket protocols you wish to support',
        #     default=None,
        # )
        # self.parser.add_argument(
        #     '--root-path',
        #     dest='root_path',
        #     help='The setting for the ASGI root_path variable',
        #     default="",
        # )
        # self.parser.add_argument(
        #     '--proxy-headers',
        #     dest='proxy_headers',
        #     help='Enable parsing and using of X-Forwarded-For and X-Forwarded-Port headers and using that as the '
        #          'client address',
        #     default=False,
        #     action='store_true',
        # )

        self.server = None

    @classmethod
    def entrypoint(cls):
        """
        Main entrypoint for external starts.
        """
        try:
            cls().run(sys.argv[1:])
        except KeyboardInterrupt:
            pass

    def run(self, args):
        """
        Pass in raw argument list and it will decode them
        and run the server.
        """
        # Decode args
        args = self.parser.parse_args(args)
        sys.path.append('.')
        if args.chdir:
            os.chdir(args.chdir)
        # print(os.getcwd())
        # foo.MyClass()
        # # Set up logging
        # logging.basicConfig(
        #     level={
        #         0: logging.WARN,
        #         1: logging.INFO,
        #         2: logging.DEBUG,
        #     }[args.verbosity],
        #     format="%(asctime)-15s %(levelname)-8s %(message)s",
        # )
        # # If verbosity is 1 or greater, or they told us explicitly, set up access log
        # access_log_stream = None
        # if args.access_log:
        #     if args.access_log == "-":
        #         access_log_stream = sys.stdout
        #     else:
        #         access_log_stream = open(args.access_log, "a", 1)
        # elif args.verbosity >= 1:
        #     access_log_stream = sys.stdout
        # # Import channel layer
        # sys.path.insert(0, ".")
        if ':' in args.channel_layer:
            module_path, object_path = args.channel_layer.split(":", 1)
        else:
            module_path = args.channel_layer
            object_path = 'channel_layer'
        print('module_path {}'.format(module_path))
        print('object_path {}'.format(object_path))
        channel_layer = importlib.import_module(module_path)
        for bit in object_path.split("."):
            channel_layer = getattr(channel_layer, bit)
        print(type(channel_layer))
        #
        # if not any([args.host, args.port, args.unix_socket, args.file_descriptor, args.socket_strings]):
        #     # no advanced binding options passed, patch in defaults
        #     args.host = DEFAULT_HOST
        #     args.port = DEFAULT_PORT
        # elif args.host and not args.port:
        #     args.port = DEFAULT_PORT
        # elif args.port and not args.host:
        #     args.host = DEFAULT_HOST
        #


        executable = '{uwsgipath} --http-socket :{port} --master --ugreen --wsgi-file ../uwsgi_asgi.py --async {async}'.format(**vars(args))
        for i in range(args.asgi_workers):
            executable += ' --mule=../worker_mule.py'  # todo, maybe I can use farm instead of a loop
        print(executable)
        p = subprocess.Popen(executable.split(' '), stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        return p.wait()


if __name__ == '__main__':
    CommandLineInterface.entrypoint()