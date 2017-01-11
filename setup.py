from setuptools import find_packages, setup
from uwsgi_asgi import __version__

setup(
    name='uwsgi_asgi',
    version=__version__,
    url='http://github.com/tovmeod/uwsgi_asgi',
    author='Avraham Seror',
    author_email='tovmeod@gmail.com',
    description="ASGI support to UWSGI.",
    long_description=open('README.rst').read(),
    license='BSD',
    keywords='uwsgi, django, channels, websocket',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'uWSGI==2.0.14'
        'Django>=1.8',
        'asgiref>=0.13',
        'daphne>=0.14.1',
    ]
)
