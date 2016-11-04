"""
HTTP Request Routing
====================

"""
import collections
import logging
import re

LOGGER = logging.getLogger(__name__)

Match = collections.namedtuple('Match', [
    'handler', 'name', 'pattern', 'suppress_logging', 'init_kwargs', 'args',
    'kwargs'
])


def match(routes, request):
    """Iterate over the list of routes, checking each route returning the
    first match that is found.

    :rtype: troika.http.route.Match

    """
    for route in routes:
        result = route.match(request.path)
        if result:
            return Match(route.handler, route.name, route.pattern,
                         route.suppress_logging, route.kwargs,
                         result.group(), result.groupdict())


class Route:
    """Specifies the association between a URI path pattern and a
    :cls:`~troika.http.RequestHandler`.

    """
    __slots__ = ('pattern', 'compiled', 'handler', 'kwargs', 'name',
                 'suppress_logging')

    def __init__(self,
                 pattern,
                 handler,
                 kwargs=None,
                 name=None,
                 suppress_logging=False):
        """Create a new Route association

        :param str pattern: The regex pattern to use for matching the path
        :param handler: Class to invoke to handle the request
        :type handler: troika.http.RequestHandler
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

    def __repr__(self):
        """Return the string representation of the route.

        :rtype: str

        """
        return '{}({}, kwargs={!r}, name={!r})'.format(
            self.__class__.__name__, self.pattern, self.kwargs, self.name)

    def match(self, value):
        """Perform pattern matching on this route.

        :param str value: The HTTP request path
        :rtype: re.Match

        """
        return self.compiled.match(value)
