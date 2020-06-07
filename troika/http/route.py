"""HTTP Request Routing"""
import dataclasses
import logging
import re
import typing

from . import handlers, server

LOGGER = logging.getLogger(__name__)

KWArgs = typing.Dict[str, typing.Union[bool, dict, int, list, str]]


class Route:
    """Web Application Route Association

    Specifies the association between a URI path pattern and a
    :class:`~troika.http.RequestHandler`.

    """

    __slots__ = ('pattern', 'compiled', 'handler', 'kwargs', 'name',
                 'suppress_logging')

    def __init__(self,
                 pattern: str,
                 handler: handlers.RequestHandler,
                 kwargs: typing.Optional[typing.Dict[str, typing.Any]] = None,
                 name: typing.Optional[str] = None,
                 suppress_logging: bool = False):
        """Create a new Route association

        :param pattern: The regex pattern to use for matching the path
        :param handler: Class to invoke to handle the request
        :param kwargs: Optional dictionary of arguments that are passed into
            the handler's constructor.
        :param name: The name for this pattern and handler combination. This
            is used by :meth:`troika.http.Application.reverse_url`.

        """
        if not pattern.endswith('$'):
            pattern += '$'
        self.pattern = pattern
        self.compiled = re.compile(pattern)
        self.handler = handler
        self.kwargs = kwargs or {}
        self.name = name
        self.suppress_logging = suppress_logging

    def __repr__(self) -> str:
        """Return the string representation of the route"""
        return '{}({}, kwargs={!r}, name={!r})'.format(
            self.__class__.__name__, self.pattern, self.kwargs, self.name)

    def match(self, value: str) -> re.Match:
        """Perform pattern matching on this route.

        :param value: The HTTP request path

        """
        return self.compiled.match(value)


@dataclasses.dataclass(frozen=True)
class RouteMatch:
    handler: handlers.RequestHandler
    name: str
    pattern: str
    suppress_logging: bool
    init_kwargs: typing.List[typing.Dict[str, typing.Any]]
    args: typing.List[str]
    kwargs: typing.Dict[str, str]


def match(routes: typing.List[Route],
          request: server.HTTPRequest) -> typing.Optional[RouteMatch]:
    """Find a route match

    Iterate over the list of routes, checking each route returning the
    first match that is found.

    """
    for route in routes:
        result = route.match(request.path)
        if result:
            return RouteMatch(
                route.handler,
                route.name,
                route.pattern,
                route.suppress_logging,
                route.kwargs,
                result.group(),
                result.groupdict())
