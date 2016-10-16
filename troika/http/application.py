import asyncio
import logging

from troika.http import \
    exceptions, handlers, server, route, transcoders, __version__

LOGGER = logging.getLogger(__name__)


class Application:

    def __init__(self, routes, settings=None, port=8000, loop=None):
        self.access_logger = logging.getLogger('troika.access')
        self.loop = loop or asyncio.get_event_loop()
        self.port = port
        self.settings = self._set_default_settings(settings or {})
        self.routes = self._compile_routes(routes)
        self.transcoders = transcoders.default()
        self.server = self._create_server()
        self.server_header = '{}/{}'.format(self.settings['server_name'],
                                            self.settings['server_version'])

    def add_transcoder(self, transcoder, mime_type=None):
        """Add a Content-Type transcoder to the application, providing the
        the mechanism for the automatic decoding of request body data and
        encoding of response bodies.

        :param transcoder: The transcoder to add
        :type transcoder: troika.http.transcoders.Transcoder
        :param str mime_type: The mime type to register the transcoder to

        """
        self.transcoders[mime_type or transcoder.MIME_TYPE] = transcoder

    def dispatch(self, request):
        match = route.match(self.routes, request)
        LOGGER.debug('Request Match: %r', match)
        try:
            return match.handler(self, request, match).execute()
        except Exception as error:
            LOGGER.exception('Error processing request: %s', error)
            raise exceptions.HTTPError(500)

    def log_request(self, handler):
        if handler.get_status() < 400:
            log_method = self.access_logger.info
        elif handler.get_status() < 500:
            log_method = self.access_logger.warning
        else:
            log_method = self.access_logger.error
        request_time = 1000.0 * handler.request.request_time()
        log_method('%d %s %.2fms', handler.get_status(),
                   handler.request_summary(), request_time)

    def run(self):
        LOGGER.info('Starting troika.http.Application v%s', __version__)
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())
        self.loop.close()
        LOGGER.debug('Exiting application.run')

    def _compile_routes(self, routes):
        compiled = []
        for value in routes:
            if isinstance(value, route.Route):
                compiled.append(value)
            else:
                compiled.append(route.Route(*value))

        # Add the default route
        compiled.append(route.Route(
            r'/.*$',
            self.settings['default_handler_class'],
            self.settings['default_handler_kwargs'],
            self.settings['default_handler_name'],
            self.settings['default_handler_suppress_logs']
        ))
        LOGGER.debug('Routes: %r', compiled)
        return compiled

    def _create_server(self):
        settings = {
            'name': self.settings['server_name'],
            'version': self.settings['server_version']
        }
        http_server = self.loop.create_server(
            lambda: server.HTTPServerProtocol(application=self,
                                              loop=self.loop),
            host='127.0.0.1', port=self.port)
        return self.loop.run_until_complete(http_server)

    def _set_default_settings(self, settings):
        """Apply default settings for non-configured values.

        :param dict settings: Settings passed in the constructor
        :rtype: dict

        """
        settings.setdefault('autoreload', False)
        settings.setdefault('compress_response', False)
        settings.setdefault('default_content_type', 'text/html; charset=UTF-8')
        settings.setdefault('default_handler_class', handlers.DefaultHandler)
        settings.setdefault('default_handler_kwargs', {})
        settings.setdefault('default_handler_name', 'default')
        settings.setdefault('default_handler_suppress_logs', False)
        settings.setdefault('log_function', self.log_request)
        settings.setdefault('serve_traceback', False)
        settings.setdefault('server_name', 'troika-http')
        settings.setdefault('server_version', __version__)
        settings.setdefault('static_path', None)
        return settings
