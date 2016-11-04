"""
Content Transcoders
===================

"""

import base64
import collections
import json
from urllib import parse
import uuid

from ietfparse import headers

try:
    import umsgpack
except ImportError:  # pragma: nocover
    umsgpack = None

try:
    import yaml
except ImportError:  # pragma: nocover
    yaml = None

from troika.http import escape

PACKABLE_TYPES = (bool, int, float)


def default():
    """Return the default transcoders to use when creating an instance of
    :cls:`troika.http.Applicaiton`.

    :rtype: list

    """
    transcoders = [
        ('text/html', Text()),
        (Text.MIME_TYPE, Text()),
        (Binary.MIME_TYPE, Binary()),
        (FormURLEncoded.MIME_TYPE, FormURLEncoded()),
        (JSON.MIME_TYPE, JSON()),
    ]
    if umsgpack:  # pragma: nocover
        transcoders.append((MessagePack.MIME_TYPE, MessagePack()))
    if yaml:  # pragma: nocover
        transcoders.append((YAML.MIME_TYPE, YAML()))
    return ([headers.parse_content_type(row[0]) for row in transcoders],
            dict(transcoders))


class Transcoder:
    """Base Transcoder Implementation that will always return values passed
    into it.

    :param str mime_type: registered content type
    :param marshall: function that marshalls/serializes a value
    :param unmarshall: function that unmarshalls/deserializes a value

    """
    MIME_TYPE = 'text/plain'

    def __init__(self, mime_type=None):
        self.mime_type = mime_type or self.MIME_TYPE

    def to_bytes(self, value):
        """Transform an object into :class:`bytes`.

        :param object value: object to encode
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`
        :raises: TypeError

        """
        return self.mime_type, self._marshall(value)

    def from_bytes(self, data_bytes):  # pragma: nocover
        """Get an object from :class:`bytes`

        :param bytes data_bytes: stream of bytes to decode
        :returns: decoded :class:`object` instance

        """
        return self._unmarshall(data_bytes)

    @staticmethod
    def _marshall(value):
        return value

    @staticmethod
    def _unmarshall(value):
        return value


class Binary(Transcoder):
    """Pack and unpack binary types."""
    MIME_TYPE = 'application/octet-stream'


class Text(Transcoder):
    """Transcodes between textual and object representations.

    This transcoder wraps functions that transcode between :class:`str`
    and :class:`object` instances.  In particular, it handles the
    additional step of transcoding into the :class:`byte` instances
    that tornado expects.

    """
    ENCODING = 'UTF-8'
    MIME_TYPE = 'text/plain'

    def __init__(self, mime_type=None, encoding=None):
        """Create a new text transcoder.

        :param str mime_type: The mime type to use
        :param str encoding: The string encoding to use
        """
        super(Text, self).__init__(mime_type)
        self.mime_type = mime_type or self.MIME_TYPE
        self.encoding = encoding or self.ENCODING

    def to_bytes(self, inst_data, encoding=None):
        """Transform an object into :class:`bytes`.

        :param object inst_data: object to encode
        :param str encoding: character set used to encode the bytes
            returned from the ``dumps`` function.  This defaults to
            :attr:`encoding`
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`

        """
        selected = encoding or self.encoding
        mime_type = '{0}; charset="{1}"'.format(self.mime_type, selected)
        dumped = self._marshall(escape.recursive_to_str(inst_data))
        return mime_type, dumped.encode(selected)

    def from_bytes(self, data, encoding=None):
        """Get an object from :class:`bytes`

        :param bytes data: stream of bytes to decode
        :param str encoding: character set used to decode the incoming
            bytes before calling the ``loads`` function.  This defaults
            to :attr:`encoding`
        :returns: decoded :class:`object` instance

        """
        return self._unmarshall(data.decode(encoding or self.encoding))


class FormURLEncoded(Text):
    """Encodes dict values as URL encoded form data with as follows:

    1. Control names and values are escaped. Space characters are replaced by
        ``+``, and then reserved characters are escaped as described in
        :rfc:`RFC1738`, section 2.2: Non-alphanumeric characters are replaced
        by ``%HH``, a percent sign and two hexadecimal digits representing the
        ASCII code of the character. Line breaks are represented as
        "CR LF" pairs (i.e., ``%0D%0A``).
    2. The control names/values are listed in the order they appear in the
        document. The name is separated from the value by ``=`` and name/value
        pairs are separated from each other by ``&``.

    """
    ENCODING = 'UTF-8'
    MIME_TYPE = 'application/x-www-form-urlencoded'

    @staticmethod
    def _marshall(value):
        """Dump a :class:`object` instance into a Form Encoded :class:`str`

        :param dict value: the object to dump
        :return: the JSON representation of :class:`object`
        :rtype: str

        """
        return parse.urlencode(
            [(k, v) for k, v in sorted(_normalize(value).items())], doseq=True)

    @staticmethod
    def _unmarshall(value):
        """Transform :class:`str` into an :class:`object` instance.

        :param str value: the UTF-8 representation of an object
        :return: the decoded :class:`object` representation

        """
        data = parse.parse_qs(value)
        for key, item in data.items():
            if isinstance(item, list) and len(item) == 1:
                data[key] = item.pop()
        return data


class JSON(Text):
    """JSON transcoder instance.

    This JSON encoder uses :func:`json.loads` and :func:`json.dumps` to
    implement JSON encoding/decoding.  The :meth:`dump_object` method is
    configured to handle types that the standard JSON module does not
    support.

    """
    ENCODING = 'UTF-8'
    MIME_TYPE = 'application/json'

    @staticmethod
    def _marshall(value):
        """Dump a :class:`value` instance into a JSON :class:`str`

        :param object value: the object to dump
        :return: the JSON representation of :class:`object`
        :rtype: str

        """
        return json.dumps(_normalize(value), separators=(',', ':'))

    @staticmethod
    def _unmarshall(value):
        """Transform :class:`str` into an :class:`object` instance.

        :param str str_repr: the UTF-8 representation of an object
        :return: the decoded :class:`object` representation

        """
        return json.loads(value)


class MessagePack(Binary):
    """This transcoder uses the `umsgpack`_ library to encode and decode
    objects according to the `MessagePack format`_.

    .. _umsgpack: https://github.com/vsergeev/u-msgpack-python
    .. _MessagePack format: http://msgpack.org/index.html

    """
    MIME_TYPE = 'application/msgpack'

    def __init__(self, mime_type=None):
        """Create a new MessagePack transcoder.

        :param str mime_type: the content type that this encoder instance
            implements. If omitted, ``application/msgpack`` is used. This
            is passed directly to the ``BinaryContentHandler`` initializer.

        :raises: RuntimeError

        """
        if umsgpack is None:  # pragma: nocache
            raise RuntimeError('MessagePack error: missing umsgpack')
        super(MessagePack, self).__init__(mime_type)

    @staticmethod
    def _marshall(value):
        """Pack `data` into a :class:`bytes` instance.

        :param object value: The object to marshall into msgpack data
        :rtype: bytes

        """
        return umsgpack.packb(_normalize(value, False))

    @staticmethod
    def _unmarshall(value):
        """Unpack a :class:`object` from a :class:`bytes` instance.

        :param bytes value: The msgpack data to unmarshall into an object
        :rtype: dict

        """
        return umsgpack.unpackb(value)


class YAML(Text):
    """Transcode objects into YAML."""
    ENCODING = 'UTF-8'
    MIME_TYPE = 'text/x-yaml'

    def __init__(self, mime_type=None, encoding=None):
        """Create a new YAML transcoder.

        :param str mime_type: the content type that this encoder instance
            implements. If omitted, ``text/x-yaml`` is used. This is
            passed directly to the ``TextContentHandler`` initializer.
        :param str encoding: the encoding to use if none is specified.
            If omitted, this defaults to ``UTF-8``. This is passed directly to
            the ``TextContentHandler`` initializer.

        """
        if yaml is None:  # pragma: nocache
            raise RuntimeError('YAML error: missing pyyaml')
        super(YAML, self).__init__(mime_type, encoding)

    @staticmethod
    def _marshall(value):
        """Dump a :class:`object` instance into a JSON :class:`str`

        :param object value: the object to dump
        :return: the JSON representation of :class:`object`
        :rtype: str

        """
        return yaml.dump(_normalize(value))

    @staticmethod
    def _unmarshall(value):
        """Transform :class:`str` into an :class:`object` instance.

        :param str value: the UTF-8 representation of an object
        :return: the decoded :class:`object` representation

        """
        return yaml.load(value)


def b64encode(value):
    """Return the value as a base64 encoded str

    :param object value: the object to encode
    :rtype: str

    """
    return base64.b64encode(value).decode('ASCII')


def _normalize(value, encode=True):
    """Called to encode unrecognized object for permissive transcoders like
    JSON and YAML. This method provides default representations for
    a number of Python language/standard library types.

    :param mixed value: the value to normalize
    :return: the normalized
    :raises TypeError: when `value` cannot be normalized

    """
    if value is None:
        return value
    elif isinstance(value, PACKABLE_TYPES):
        return value
    elif isinstance(value, uuid.UUID):
        return str(value)
    elif isinstance(value, bytes) and encode:
        return b64encode(value)
    elif isinstance(value, bytearray):
        return b64encode(value) if encode else bytes(value)
    elif isinstance(value, memoryview):
        return b64encode(value) if encode else value.tobytes()
    elif hasattr(value, 'isoformat'):
        return value.isoformat()
    elif isinstance(value, bytes) or isinstance(value, str):
        return value
    elif isinstance(value, (collections.Sequence, collections.Set)):
        return [_normalize(item) for item in value]
    elif isinstance(value, collections.Mapping):
        return dict((k, _normalize(v)) for k, v in value.items())
    raise TypeError('{} is not supported'.format(value.__class__.__name__))
