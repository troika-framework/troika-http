"""HTTP Server and Request/Response Definitions"""

import asyncio
from http import cookies
import datetime
import functools
import ipaddress
import logging
import numbers
from urllib import parse
import re
from http.client import responses
import time
from email import utils

import httptools

LOGGER = logging.getLogger(__name__)

_HEADERS_END = [b'\r\n']
_INVALID_HEADER_CHAR_RE = re.compile(r'[\x00-\x1f]')


class HTTPRequest:

    def __init__(self, transport):
        self._finish_time = None
        self._start_time = time.time()

        self.transport = transport

        self.remote_ip = transport.get_extra_info('peername')[0]
        self.version = None
        self.method = None
        self.uri = None
        self.protocol = 'http'
        self.host = None
        self.query = None
        self.headers = {}
        self.body = None

        self.arguments = None
        self.query_arguments = None
        self.body_arguments = None
        self.cookies = None
        self.response = None

    def __repr__(self):
        parts = {'protocol', 'host', 'method', 'uri', 'version', 'remote_ip'}
        args = ', '.join(
            ['{!s}={!r}'.format(k, getattr(self, k)) for k in parts])
        return '{}({}, headers={!r})'.format(self.__class__.__name__, args,
                                             self.headers)

    def full_url(self):
        return '{}://{}{}'.format(self.protocol, self.host, self.uri)

    def request_time(self):
        return (self._finish_time or time.time()) - self._start_time

    def finish(self):
        if self.finished:
            raise RuntimeError('Request is already finished')

        self._finish_time = time.time()
        self.transport.close()

    @property
    def finished(self):
        return self._finish_time is not None

    def send_response(self):
        if 'Content-Length' not in self.response.headers:
            self.response.headers['Content-Length'] = len(self.response.body)
        self.response.write_headers()
        self.response.write_body()
        self.finish()


class HTTPResponse:

    body = b''
    status_code = 200
    phrase = b'OK'

    def __init__(self, http_version, transport, server_header,
                 default_content_type):
        self.default_content_type = default_content_type
        self.headers_written = False
        self.http_version = http_version
        self.server_header = server_header
        self.transport = transport
        self.headers = self.default_headers()

    def clear(self):
        self.headers = self.default_headers()
        self.phrase = b'OK'
        self.status_code = 200
        self.body = b''

    def default_headers(self):
        return {
            'Server': self.server_header,
            'Content-Type': self.default_content_type,
            'Date': utils.formatdate()
        }

    def flush(self):
        if not self.headers_written:
            self.write_headers()
        self.write_body()
        self.body = b''

    def write_headers(self):
        if self.headers_written:
            raise RuntimeError('Headers already written')
        self.transport.write(
            b''.join(['HTTP/{} {} {}\r\n'.format(
                self.http_version, self.status_code,
                responses[self.status_code]).encode('utf-8')
            ] + [
                '{}: {}\r\n'.format(k, v).encode('utf-8')
                for k, v in _normalize_headers(self.headers).items()
            ] + _HEADERS_END))
        self.headers_written = True

    def write_body(self):
        self.transport.write(self.body)


class HTTPServerProtocol(asyncio.Protocol):

    def __init__(self, *, application, loop):
        self.application = application
        self.loop = loop
        self.parser = None
        self.request = None
        self.transport = None

    def connection_made(self, transport):
        self.parser = httptools.HttpRequestParser(self)
        self.request = HTTPRequest(transport)

    def connection_lost(self, exc):
        if exc:
            LOGGER.debug('Connection Lost: %r', exc)

    def data_received(self, data):
        self.parser.feed_data(data)

    def eof_received(self):
        LOGGER.debug('EOF Received')

    def on_url(self, url):
        self.request.uri = url.decode('utf-8')
        parsed = parse.urlsplit(url)
        self.request.path = parse.unquote(parsed.path.decode('utf-8'))
        self.request.query = parsed.query.decode('utf-8')
        self.request.query_arguments = parse.parse_qs(parsed.query)

    def on_header(self, name, value):
        key = _normalize_header_key(name.decode('utf-8'))
        if key == 'Cookie':
            self.request.cookies = cookies.BaseCookie(value.decode('utf-8'))
        elif key in {'X-Forwarded-For', 'X-Real-Ip'}:
            try:
                self.request.remote_ip = \
                    str(ipaddress.ip_address(value.split(',')[-1].strip()))
            except ValueError:
                pass
        elif key in {'X-Scheme', 'X-Forwarded-Proto'}:
            self.request.protocol = value.decode('utf-8')
        elif key == 'Host':
            self.request.host = value.decode('utf-8')
        self.request.headers[key] = value.decode('utf-8')

    def on_body(self, value):
        self.request.body = value

    def on_headers_complete(self):
        self.request.version = self.parser.get_http_version()
        self.request.method = self.parser.get_method().decode('utf-8')

    def on_message_complete(self):
        self.request.response = HTTPResponse(
            self.request.version, self.request.transport,
            self.application.server_header,
            self.application.settings['default_content_type'])
        self.loop.create_task(self.application.dispatch(self.request))


def _normalize_headers(headers):
    normalized = {}
    for key, value in headers.items():
        normalized[_normalize_header_key(key)] = _normalize_header_value(value)
    return normalized


@functools.lru_cache(30)
def _normalize_header_key(value):
    return '-'.join([part.capitalize() for part in value.split('-')])


def _normalize_header_value(value):
    if isinstance(value, str):
        pass
    elif isinstance(value, bytes):
        value = value.decode('latin1')
    elif isinstance(value, numbers.Integral):
        value = str(value)
    elif isinstance(value, datetime.datetime):
        value = utils.format_datetime(value)
    else:
        raise ValueError('Unsupported header value type: {}'.format(
            type(value)))
    if _INVALID_HEADER_CHAR_RE.match(value):
        raise ValueError('Unsafe header value: {!r}'.format(value))
    return value
