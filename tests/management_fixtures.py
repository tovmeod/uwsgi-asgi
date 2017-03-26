import os
import random
import string

import pytest
from rabbitmq_admin import AdminAPI


@pytest.fixture(scope='session')
def environment():
    """Dict of the interesting environment variables."""

    environment = {
        'RABBITMQ_HOST': 'localhost',
        'RABBITMQ_PORT': '5672',
        'RABBITMQ_USER': 'guest',
        'RABBITMQ_PASSWORD': 'guest',
        'RABBITMQ_MANAGEMENT_PORT': '15672',
    }
    for varname, default in environment.items():
        environment[varname] = os.environ.get(varname, default)
    return environment


@pytest.fixture(scope='session')
def management(environment):
    """RabbitMQ Management Client."""

    hostname = environment['RABBITMQ_HOST']
    port = environment['RABBITMQ_MANAGEMENT_PORT']
    user = environment['RABBITMQ_USER']
    password = environment['RABBITMQ_PASSWORD']
    return AdminAPI('http://%s:%s' % (hostname, port), (user, password))


@pytest.fixture(scope='session')
def remove_vhost(management):
    """
    Remove all virtual hosts in the RabbitMQ which was created during
    test run.
    """

    vhosts = []
    yield vhosts
    for vhost in vhosts:
        management.delete_vhost(vhost)


@pytest.fixture
def virtual_host(management, remove_vhost, environment):
    """Create randomly named virtual host."""

    user = environment['RABBITMQ_USER']
    vhost = ''.join(random.choice(string.ascii_letters) for i in range(8))
    management.create_vhost(vhost)
    management.create_user_permission(user, vhost)
    remove_vhost.append(vhost)
    return vhost


@pytest.fixture
def rabbitmq_url(virtual_host, environment):
    """
    Create randomly named virtual host and return fully qualified url
    for it.
    """

    host = environment['RABBITMQ_HOST']
    port = environment['RABBITMQ_PORT']
    url = 'amqp://%s:%s/%s' % (host, port, virtual_host)
    return url
