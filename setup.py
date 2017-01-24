from setuptools import find_packages, setup

from uwsgi_asgi import __version__  # NOQA isort:skip

setup(
    name='uwsgi_asgi',
    version=__version__,
    url='http://github.com/tovmeod/uwsgi_asgi',
    author='Avraham Seror',
    author_email='tovmeod@gmail.com',
    description="ASGI support to UWSGI.",
    long_description=open('README.rst').read(),
    license='BSD',
    keywords='uwsgi django channels websocket asgi',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=[
        'uWSGI>=2.0.14',
        'six',
        'u-msgpack-python>=2.3.0',
    ],
    tests_require=open('testproj/requirements.txt').readlines()+['websocket-client>=0.40.0', 'pytest>=3.0.5',
                                                                 'pytest-timeout>=1.2.0'],
    entry_points={'console_scripts': [
        'uwsgiasgi = uwsgi_asgi.cli:CommandLineInterface.entrypoint',
    ]},
    classifiers=[
        'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        'Operating System :: POSIX',
        "Programming Language :: Python",
        # 'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        "Framework :: Django",
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server'
        'Topic :: Internet :: WWW/HTTP :: ASGI :: Server'
    ]
)
