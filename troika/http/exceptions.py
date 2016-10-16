"""
Troika HTTP Exceptions
======================

"""
import http


class Finish(Exception):
    pass


class HTTPError(Exception):

    def __init__(self, status_code, reason=None, message=None):
        self.status_code = status_code
        self.reason = reason or http.HTTPStatus(status_code).phrase
        self.message = message or http.HTTPStatus(status_code).description
