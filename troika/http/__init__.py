"""Troika HTTP Application Framework"""

try:
    from troika.http.application import Application
    from troika.http.handlers import RequestHandler, RedirectHandler
    from troika.http.route import Route
    from troika.http.version import __version__
except ImportError as error:  # pragma: nocover
    # Allows for importing the version when setting up
    Application = None
    RedirectHandler = None
    RequestHandler = None
    Route = None
    __version__ = None

from troika.http.exceptions import *

__all__ = [
    '__version__',
    'application',
    'exceptions',
    'handlers',
    'route',
    'server',
    'Application',
    'Finish',
    'HTTPError',
    'RedirectHandler',
    'RequestHandler',
    'Route'
]
