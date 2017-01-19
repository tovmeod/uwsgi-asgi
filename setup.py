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
        'uWSGI==2.0.14',
        'six',
        'u-msgpack-python==2.3.0',
    ],
    tests_require=open('testproj/requirements.txt').readlines()+['websocket-client==0.40.0', 'pytest==3.0.5',
                                                                 'pytest-timeout==1.2.0'],
)
