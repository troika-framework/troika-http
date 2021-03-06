"""Troika HTTP Exceptions"""
import http


class HTTPException(Exception):
    """Base exception for all Troika HTTP exceptions"""


class Finish(HTTPException):
    """Raise to finish processing the HTTP Request"""


class HTTPError(HTTPException):
    """HTTP Request Error

    Raise to finish the HTTP Request handling, returning an HTTP error
    as the response.

    Status codes from the following RFCs are all observed:

        * RFC 7231: Hypertext Transfer Protocol (HTTP/1.1), obsoletes 2616
        * RFC 6585: Additional HTTP Status Codes
        * RFC 3229: Delta encoding in HTTP
        * RFC 4918: HTTP Extensions for WebDAV, obsoletes 2518
        * RFC 5842: Binding Extensions to WebDAV
        * RFC 7238: Permanent Redirect
        * RFC 2295: Transparent Content Negotiation in HTTP
        * RFC 2774: An HTTP Extension Framework

    """
    def __init__(self,
                 status_code: int,
                 phrase: str = None,
                 description: str = None):
        """Raise a new HTTP Error

        If``phrase`` or ``description`` are omitted and the default values
        will be used.

        :param status_code: The HTTP status code
        :param phrase: Optionally override the HTTP response phrase
        :param description: Optionally override the HTTP response
            description

        """
        super(HTTPError, self).__init__()
        self.status_code = status_code
        self._status = http.HTTPStatus(status_code, phrase, description)

    @property
    def description(self):
        """Return the HTTP response description

        :rtype: str

        """
        return self._status.description

    @property
    def phrase(self):
        """Return the HTTP response phrase

        :rtype: str

        """
        return self._status.phrase
