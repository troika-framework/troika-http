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

    SUPPORTED_METHODS = {
        'DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT'
    }

    def __init__(self, application, request, route):
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
        self.logger.debug('Initializing')

    def prepare(self):
        self.logger.debug('Preparing %r', self.request)

    def delete(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def get(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def head(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def options(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def patch(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def post(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def put(self, *args, **kwargs):
        raise exceptions.HTTPError(405)

    def on_connection_closed(self):
        pass

    def on_finished(self):
        pass

    @property
    def name(self):
        return self.route.name or self.__class__.__name__

    def clear(self):
        self.request.response.clear()

    def clear_header(self, key):
        if key in self.request.response.headers:
            del self.request.response.headers[key]

    def finish(self, chunk=None):
        if self.request.finished:
            raise RuntimeError('Request is already finished')
        if chunk:
            self.write(chunk)

    def flush(self):
        return self.request.response.flush()

    @functools.lru_cache(1)
    def get_body_arguments(self):
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
                parsed,
                self.application.transcoders[0])
        except errors.NoMatch:
            raise ValueError(
                'Cant transcode a Content-Type of {}'.format(
                    self.request.headers.get('Content-Type', '')))
        key = '/'.join([selected.content_type, selected.content_subtype])
        transcoder = self.application.transcoders[1][key]
        return transcoder.from_bytes(self.request.body)

    @functools.lru_cache(1)
    def get_request_language(self, default='en_US'):
        if 'Accept-Language' not in self.request.headers:
            return default
        #languages = headers.parse_accept_language(
        #    self.request.headers['Accept-Language'])
        #return languages[0] if languages else default

    @functools.lru_cache(1)
    def get_request_encoding(self, default=None):
        if 'Accept-Encoding' not in self.request.headers:
            return default

    def get_status(self):
        return self.request.response.status_code

    def redirect(self, url, permanent=False, status=None):
        status = status or 301 if permanent else 302
        self.set_status(status)
        self.set_header('Location', url)
        self.finish()

    def require_setting(self, name):
        if not self.application.get(name):
            raise RuntimeError('Missing required setting {!r}'.format(name))

    def send_error(self, status_code, reason=None, message=None, **kwargs):
        self.write_error(
            exceptions.HTTPError(status_code, reason, message), **kwargs)

    def set_header(self, key, value):
        self.request.response.headers[key] = value

    def set_status(self, status_code, reason=None):
        self.request.response.status_code = status_code
        self.request.response.reason = reason

    def write(self, chunk):
        if isinstance(chunk, str):
            chunk = chunk.encode('utf-8')
        elif isinstance(chunk, dict):
            transcoder = self._get_response_transcoder()
            content_type, chunk = transcoder.to_bytes(chunk)
            self.set_header('Content-Type', content_type)
        elif not isinstance(chunk, bytes):
            raise ValueError(
                'write() only accepts dict, str, or bytes objects')
        self.request.response.body += chunk

    def write_error(self, error, **kwargs):
        """Overwrite to implement custom error pages. This implementaiton
        will send a HTML error page if the default content type is `text/html`,
        otherwise it will send the error as an object in the negotiated
        format as specified in the `Accept` header.

        :param troika.http.HTTPError error: The error to write
        :param dict kwargs: User provided arguments to pass in for rendering

        """
        values = {
            'status_code': error.status_code,
            'exception': error.__class__.__name__,
            'reason': error.reason,
            'message': error.message
        }
        values.update(kwargs)
        stack = []
        if kwargs.get('exc_info'):
            if self.settings['serve_traceback']:
                stack = [l for l in
                         traceback.format_exception(*kwargs['exc_info'])]
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
        # process the request. This is not a normal docstring so it is not
        # exposed in the user documentaiton
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
        result = self.prepare()
        if result:
            yield from result

        if not self.request.finished:
            method = getattr(self, self.request.method.lower())
            result = method()
            if result:
                yield from result

    @functools.lru_cache(1)
    def _get_response_transcoder(self):
        """Figure out what content type will be used in the response.

        :rtype: troika.http.transcoders.Transcoder

        """
        content_type = self._get_response_content_type()
        if content_type:
            return self.application.transcoders[1].get(content_type)

    @functools.lru_cache(1)
    def _get_response_content_type(self):
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

    def _handle_request_exception(self, error, exc_info):
        if isinstance(error, exceptions.Finish):
            if not self.request.finished:
                self.finish(*error.args)
        elif isinstance(error, exceptions.HTTPError):
            self.write_error(error=error)
        else:
            LOGGER.exception('Uncaught exception: %s', error,
                             exc_info=exc_info)
            self.write_error(exceptions.HTTPError(500), exc_info=exc_info)


class DefaultHandler(RequestHandler):
    """Implements a RequestHandler that will raise 404. This should always
    be used in the last Route in an application and is appended to the route
    automatically.

    """
    def prepare(self):
        raise exceptions.HTTPError(404)


class RedirectHandler(RequestHandler):
    """Implements a RequestHandler that can be included in the application
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
