"""HTTP Request Handlers"""

import asyncio
import functools
import logging
import sys
import traceback

from ietfparse import algorithms, errors, headers

from troika.http import exceptions

LOGGER = logging.getLogger(__name__)

HTML_ERROR_TEMPLATE = """\
<html>
  <head><title>{status_code}: {reason}</title></head>
  <body>
    <h1>{status_code}: {reason}</h1>
    <p>{message}</p>
    <pre>{traceback}</pre>
  </body>
</html>
"""


class RequestHandler:

    """Respond to HTTP Requests"""

    def __init__(self, application, request, route):
        """Create a new RequestHandler instance.

        :param application: The troika HTTP application
        :type: troika.http.application.Application
        :param request: The HTTP request the handler is responding to
        :type: troika.http.server.HTTPRequest
        :param route: The matched route used to invoke this handler
        :type: troika.route.Match

        """
        self.application = application
        self.logger = logging.getLogger(
            '{}.{}'.format(__name__, self.__class__.__name__))
        self.request = request
        self.route = route

    @property
    def settings(self):
        """An alias for :attr:`troika.http.Application.settings`

        :rtype: dict

        """
        return self.application.settings

    def initialize(self, **kwargs):
        """Initialize the RequestHandler

        :param kwargs:

        """
        self.logger.debug('Initializing')

    def prepare(self):
        """

        """
        self.logger.debug('Preparing %r', self.request)

    def on_connection_closed(self):
        """Invoked if the connection is closed when not finished"""
        pass

    def on_finished(self):
        """Invoked when the Response has been sent"""
        pass

    @property
    def name(self):
        """Return the name of the route or the class if the route name is not
        set.

        :rtype: str

        """
        return self.route.name or self.__class__.__name__

    def clear(self):
        """Clear response content and headers"""
        self.request.response.clear()

    def clear_header(self, field):
        """Remove a header field by name.

        :param str field: The header field name

        """
        if field in self.request.response.headers:
            del self.request.response.headers[field]

    def finish(self, chunk=None):
        """Complete the request response.

        :param mixed chunk:

        """
        if self.request.finished:
            raise RuntimeError('Request is already finished')
        if chunk:
            self.write(chunk)

    def flush(self):
        """Flush the output buffer"""
        return self.request.response.flush()

    @functools.lru_cache(1)
    def get_body_arguments(self):
        """Parse the request body

        Use the configured transcoders to parse the content using the
        ``Content-Type`` header field to determine which transcoder to use.

        :rtype: dict

        """
        if not self.request.body:
            return None
        parsed = headers.parse_content_type(
            self.request.headers.get('Content-Type', ''))
        if not parsed:
            return None
        if not isinstance(parsed, tuple):
            parsed = parsed,
        try:
            selected, _ = algorithms.select_content_type(
                parsed, self.application.transcoders[0])
        except errors.NoMatch:
            raise ValueError('Cant transcode a Content-Type of {}'.format(
                self.request.headers.get('Content-Type', '')))
        key = '/'.join([selected.content_type, selected.content_subtype])
        transcoder = self.application.transcoders[1][key]
        return transcoder.from_bytes(self.request.body)

    @functools.lru_cache(1)
    def get_request_language(self):
        """Return the language specified in the ``Accept-Language`` header.

        If it is not specified in the request, the configured default value
        will be returned.

        :rtype: str

        """
        if 'Accept-Language' not in self.request.headers:
            return self.settings['default-language']
        languages = headers.parse_accept_language(
            self.request.headers['Accept-Language'])
        return languages[0] if languages else self.settings['default-language']

    @functools.lru_cache(1)
    def get_request_encoding(self):
        """Return the value of the ``Accept-Encoding`` header.

        :rtype: str

        """
        if 'Accept-Encoding' not in self.request.headers:
            return self.settings['default-encoding']
        encodings = headers.parse_accept_encoding(
            self.request.headers['Accept-Encoding'])
        return encodings[0] if encodings else self.settings['default-encoding']

    def get_status(self):
        """Return the currently set status code for the HTTP response.

        :rtype: int

        """
        return self.request.response.status_code

    def redirect(self, url, permanent=False, status=None):
        status = status or 301 if permanent else 302
        self.set_status(status)
        self.set_header('Location', url)
        self.finish()

    def require_setting(self, name):
        """Use to ensure that a specific application setting exists.

        If the setting does not exist, the request handler will return a
        ``503`` response to the client and log the error.

        :param str name: The setting name
        :raises: troika.exceptions.HTTPError

        """
        if not self.application.get(name):
            self.logger.critical(
                'Missing required setting %s for %s', name, self.name)
            raise exceptions.HTTPError(503)

    def send_error(self, status_code, reason=None, message=None, **kwargs):
        self.write_error(
            exceptions.HTTPError(status_code, reason, message), **kwargs)

    def set_header(self, field, value):
        """Set a HTTP response header field.

        :param str field: The response header field name
        :param str value: The response header field value

        """
        self.request.response.headers[field] = value

    def set_status(self, status_code, phrase=None):
        """Set the response status code

        If the response reason is not set, the default will be used

        :param int status_code:
        :param str phrase: Optional response phrase

        """
        self.request.response.status_code = status_code
        self.request.response.phrase = phrase

    def write(self, chunk):
        """Write the HTTP response body content.

        :param mixed chunk: The content to write

        """
        if isinstance(chunk, str):
            chunk = chunk.encode('utf-8')
        elif isinstance(chunk, dict):
            ctype, chunk = self._get_response_transcoder().to_bytes(chunk)
            self.set_header('Content-Type', ctype)
        elif not isinstance(chunk, bytes):
            raise ValueError(
                'write() only accepts dict, str, or bytes objects')
        self.request.response.body += chunk

    def write_error(self, error, **kwargs):
        """Overwrite to implement custom error pages.

        This implementaiton will send a HTML error page if the default
        content type is `text/html`, otherwise it will send the error as an
        object in the negotiated format as specified in the `Accept` header.

        :param troika.http.HTTPError error: The error to write
        :param dict kwargs: User provided arguments to pass in for rendering

        """
        values = {
            'status_code': error.status_code,
            'exception': error.__class__.__name__,
            'phrase': error.phrase,
            'description': error.description
        }
        values.update(kwargs)
        stack = []
        if kwargs.get('exc_info'):
            if self.settings['serve_traceback']:
                stack = [
                    l for l in traceback.format_exception(*kwargs['exc_info'])
                ]
            del kwargs['exc_info']

        content_type = self._get_response_content_type()
        LOGGER.debug('Response should return: %s', content_type)
        if content_type.startswith('text/html'):
            self.set_header('Content-Type', content_type)
            values['traceback'] = '\n'.join(stack)
            self.finish(HTML_ERROR_TEMPLATE.format(**values))
        else:
            values['traceback'] = stack
            self.finish(values)

    @asyncio.coroutine
    def execute(self):
        # Method invoked by :meth:`troika.http.Application.dispatch` to
        # process the request.
        self.logger.debug('Executing %r', self.request)
        result = self.initialize(**self.route.init_kwargs)
        if result:
            yield from result

        try:
            yield from self._execute()
        except Exception as error:
            exc_info = sys.exc_info()
            self._handle_request_exception(error, exc_info)

        self.request.send_response()
        if not self.route.suppress_logging:
            self.application.log_request(self)

        result = self.on_finished()
        if result:
            yield from result

    def request_summary(self):
        # Invoked by :meth:`troika.http.RequestHandler.execute` to get the
        # summary information for request logging
        return '{} {} ({})'.format(self.request.method, self.request.uri,
                                   self.request.remote_ip)

    @asyncio.coroutine
    def _execute(self):
        """Prepare and execute the request

        Invoked by :meth:`troika.http.RequestHandler.execute` to execute
        the :meth:`troika.http.RequestHandler.prepare` and the
        :meth:`troika.http.RequestHandler.verb` method, where ``verb`` is
        the HTTP verb of the request.

        """
        result = self.prepare()
        if result:
            yield from result

        if not self.request.finished:
            method = getattr(self, self.request.method.lower(), None)
            if not method:
                raise exceptions.HTTPError(405)
            result = method(*self.route.args, **self.route.kwargs)
            if result:
                yield from result

    @functools.lru_cache(1)
    def _get_response_content_type(self):
        """Detect the requested Content-Type by parsing the ``Accept`` header.

        :rtype: str

        """
        accept = self.request.headers.get('Accept')
        if accept == '*/*' or not accept:
            accept = self.settings['default_content_type']
        acceptable = headers.parse_accept(accept)
        try:
            selected, _ = algorithms.select_content_type(
                acceptable, self.application.transcoders[0])
        except errors.NoMatch:
            return self.settings['default_content_type']
        else:
            return '/'.join([selected.content_type, selected.content_subtype])

    @functools.lru_cache(1)
    def _get_response_transcoder(self):
        """Figure out what content type will be used in the response.

        :rtype: troika.http.transcoders.Transcoder

        """
        content_type = self._get_response_content_type()
        if content_type:
            return self.application.transcoders[1].get(content_type)

    def _handle_request_exception(self, error, exc_info):
        if isinstance(error, exceptions.Finish):
            if not self.request.finished:
                self.finish(*error.args)
        elif isinstance(error, exceptions.HTTPError):
            self.write_error(error=error)
        else:
            LOGGER.exception(
                'Uncaught exception: %s', error, exc_info=exc_info)
            self.write_error(exceptions.HTTPError(500), exc_info=exc_info)


class DefaultHandler(RequestHandler):

    """Default HTTP Response

    Implements a RequestHandler that will raise 404. This should always
    be used in the last Route in an application and is appended to the route
    automatically.

    """

    def prepare(self):
        raise exceptions.HTTPError(404)


class RedirectHandler(RequestHandler):

    """Redirect HTTP Requests

    Implements a RequestHandler that can be included in the application
    routes to automatically redirect to another URL.

    You must provide the ``url`` keyword argument for it to work properly.
    Provide the ``permanent`` keyword argument as a bool to indicate if a
    ``301`` status should be returned instead of a ``302``.

    Example:

    .. code:: python

        from troika import http

        application = http.Application([
            ('/', http.RedirectHandler, {'url': 'https://www.google.com'})
        ])
        application.run()

    """

    def initialize(self, url, permanent=False):
        self._url = url
        self._permanent = permanent

    def get(self):
        self.redirect(self._url, permanent=self._permanent)
