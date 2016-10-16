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

    def __init__(self, mime_type=None, marshall=None, unmarshall=None):
        self.mime_type = mime_type
        self._marshall = marshall or self.to_bytes
        self._unmarshall = unmarshall or self.from_bytes

    def to_bytes(self, value, encoding=None):
        """Transform an object into :class:`bytes`.

        :param object value: object to encode
        :param str encoding: character set used to encode the bytes
            returned from the ``dumps`` function.  This defaults to
            :attr:`default_encoding`
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`
        :raises: TypeError

        """
        return self.mime_type, self._marshall(value)

    def from_bytes(self, data_bytes, encoding=None):  # pragma: nocover
        """Get an object from :class:`bytes`

        :param bytes data_bytes: stream of bytes to decode
        :param str encoding: encoding to apply when
            transcoding from the underlying body :class:`byte`
            instance when performing text transcoding
        :returns: decoded :class:`object` instance

        """
        return self._unmarshall(data_bytes)


class Binary(Transcoder):
    """Pack and unpack binary types.

    :param str mime_type: registered content type
    :param marshall: function that transforms an object instance
        into :class:`bytes`
    :param unmarshall: function that transforms :class:`bytes`
        into an object instance

    """
    MIME_TYPE = 'application/octet-stream'

    def __init__(self, mime_type=MIME_TYPE, marshall=None, unmarshall=None):
        super(Binary, self).__init__(mime_type, marshall, unmarshall)


class Text(Transcoder):
    """Transcodes between textual and object representations.

    This transcoder wraps functions that transcode between :class:`str`
    and :class:`object` instances.  In particular, it handles the
    additional step of transcoding into the :class:`byte` instances
    that tornado expects.

    :param str mime_type: registered content type
    :param marshall: function that transforms an object instance
        into a :class:`str`
    :param unmarshall: function that transforms a :class:`str`
        into an object instance
    :param str default_encoding: encoding to apply when
        transcoding from the underlying body :class:`byte`
        instance

    """
    ENCODING = 'UTF-8'
    MIME_TYPE = 'text/plain'

    def __init__(self, mime_type=MIME_TYPE, marshall=None, unmarshall=None,
                 default_encoding=ENCODING):
        super(Text, self).__init__(mime_type, marshall, unmarshall)
        self.mime_type = mime_type
        self.default_encoding = default_encoding

    def to_bytes(self, inst_data, encoding=None):
        """Transform an object into :class:`bytes`.

        :param object inst_data: object to encode
        :param str encoding: character set used to encode the bytes
            returned from the ``dumps`` function.  This defaults to
            :attr:`default_encoding`
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`

        """
        selected = encoding or self.default_encoding
        mime_type = '{0}; charset="{1}"'.format(self.mime_type, selected)
        dumped = self._marshall(escape.recursive_to_str(inst_data))
        return mime_type, dumped.encode(selected)

    def from_bytes(self, data, encoding=None):
        """Get an object from :class:`bytes`

        :param bytes data: stream of bytes to decode
        :param str encoding: character set used to decode the incoming
            bytes before calling the ``loads`` function.  This defaults
            to :attr:`default_encoding`
        :returns: decoded :class:`object` instance

        """
        return self._unmarshall(data.decode(encoding or self.default_encoding))


class JSON(Text):
    """JSON transcoder instance.

    This JSON encoder uses :func:`json.loads` and :func:`json.dumps` to
    implement JSON encoding/decoding.  The :meth:`dump_object` method is
    configured to handle types that the standard JSON module does not
    support.
    .. attribute:: dump_options
       Keyword parameters that are passed to :func:`json.dumps` when
       :meth:`.dumps` is called.  By default, the :meth:`dump_object`
       method is enabled as the default object hook.
    .. attribute:: load_options
       Keyword parameters that are passed to :func:`json.loads` when
       :meth:`.loads` is called.


    :param str mime_type: the content type that this encoder instance
        implements. If omitted, ``application/json`` is used. This is
        passed directly to the ``TextContentHandler`` initializer.
    :param str default_encoding: the encoding to use if none is specified.
        If omitted, this defaults to ``UTF-8``. This is passed directly to
        the ``TextContentHandler`` initializer.

    """
    ENCODING = 'UTF-8'
    MIME_TYPE = 'application/json'

    def __init__(self, mime_type=MIME_TYPE, default_encoding=ENCODING):
        super(JSON, self).__init__(
            mime_type, self.marshall, self.unmarshall, default_encoding)
        self.marshall_options = {
            'default': self.dump_object,
            'separators': (',', ':')
        }
        self.unmarshall_options = {}

    def marshall(self, obj):
        """Dump a :class:`object` instance into a JSON :class:`str`

        :param object obj: the object to dump
        :return: the JSON representation of :class:`object`
        :rtype: str

        """
        return json.dumps(normalize(obj), **self.marshall_options)

    def unmarshall(self, str_repr):
        """Transform :class:`str` into an :class:`object` instance.

        :param str str_repr: the UTF-8 representation of an object
        :return: the decoded :class:`object` representation

        """
        return json.loads(str_repr, **self.unmarshall_options)

    @staticmethod
    def dump_object(obj):
        """Called to encode unrecognized object.

        :param object obj: the object to encode
        :return: the encoded object
        :raises TypeError: when `obj` cannot be encoded

        This method is passed as the ``default`` keyword parameter
        to :func:`json.dumps`.  It provides default representations for
        a number of Python language/standard library types.

        +----------------------------+---------------------------------------+
        | Python Type                | String Format                         |
        +----------------------------+---------------------------------------+
        | :class:`bytes`,            | Base64 encoded string.                |
        | :class:`bytearray`,        |                                       |
        | :class:`memoryview`        |                                       |
        +----------------------------+---------------------------------------+
        """
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return base64.b64encode(obj).decode('ASCII')
        raise TypeError('{!r} is not JSON serializable'.format(obj))


class MessagePack(Binary):
    """This transcoder uses the `umsgpack`_ library to encode and decode
    objects according to the `MessagePack format`_.

    .. _umsgpack: https://github.com/vsergeev/u-msgpack-python
    .. _MessagePack format: http://msgpack.org/index.html

    :param str mime_type: the content type that this encoder instance
        implements. If omitted, ``application/msgpack`` is used. This
        is passed directly to the ``BinaryContentHandler`` initializer.

    :raises: RuntimeError

    """
    MIME_TYPE = 'application/msgpack'

    def __init__(self, mime_type=MIME_TYPE):
        if umsgpack is None:
            raise RuntimeError('MessagePack error: missing umsgpack')
        super(MessagePack, self).__init__(
            mime_type, self.marshall, self.unmarshall)

    def marshall(self, value):
        """Pack `data` into a :class:`bytes` instance.

        :param object value: The object to marshall into msgpack data
        :rtype: bytes

        """
        return umsgpack.packb(normalize(value))

    def normalize(self, value):
        """Convert `value` into something that umsgpack likes.

        This message is called to recursively normalize before invoking
        :meth:`.packb`.

        """
        if value is None:
            return value
        elif isinstance(value, PACKABLE_TYPES):
            return value
        elif isinstance(value, uuid.UUID):
            return str(value)
        elif isinstance(value, bytearray):
            return bytes(value)
        elif isinstance(value, memoryview):
            return value.tobytes()
        elif hasattr(value, 'isoformat'):
            return value.isoformat()
        elif isinstance(value, bytes) or isinstance(value, str):
            return value
        elif isinstance(value, (collections.Sequence, collections.Set)):
            return [self.normalize(item) for item in value]
        elif isinstance(value, collections.Mapping):
            return dict((k, self.normalize(v)) for k, v in value.items())
        raise TypeError('{} is not supported'.format(value.__class__.__name__))

    def unmarshall(self, data):
        """Unpack a :class:`object` from a :class:`bytes` instance.

        :param bytes data: The msgpack data to unmarshall into an object
        :rtype: dict

        """
        return umsgpack.unpackb(data)


class YAML(Text):
    """Transcode objects into YAML

    :param str mime_type: the content type that this encoder instance
        implements. If omitted, ``text/x-yaml`` is used. This is
        passed directly to the ``TextContentHandler`` initializer.
    :param str default_encoding: the encoding to use if none is specified.
        If omitted, this defaults to ``UTF-8``. This is passed directly to
        the ``TextContentHandler`` initializer.

    """
    ENCODING = 'UTF-8'
    MIME_TYPE = 'text/x-yaml'

    def __init__(self, mime_type=MIME_TYPE, default_encoding=ENCODING):
        if yaml is None:
            raise RuntimeError('YAML error: missing pyyaml')
        super(YAML, self).__init__(
            mime_type, self.marshall, self.unmarshall, default_encoding)

    def marshall(self, value):
        """Dump a :class:`object` instance into a JSON :class:`str`

        :param object value: the object to dump
        :return: the JSON representation of :class:`object`
        :rtype: str

        """
        return yaml.dump(normalize(value))

    def unmarshall(self, value):
        """Transform :class:`str` into an :class:`object` instance.

        :param str value: the UTF-8 representation of an object
        :return: the decoded :class:`object` representation

        """
        return yaml.load(value)


class FormURLEncoded(Text):

    ENCODING = 'UTF-8'
    MIME_TYPE = 'application/x-www-form-urlencoded'

    def __init__(self, mime_type=MIME_TYPE, default_encoding=ENCODING):
        super(FormURLEncoded, self).__init__(
            mime_type, self.marshall, self.unmarshall, default_encoding)

    def marshall(self, value):
        """Dump a :class:`object` instance into a JSON :class:`str`

        :param object value: the object to dump
        :return: the JSON representation of :class:`object`
        :rtype: str

        """
        return parse.urlencode(normalize(value))

    def unmarshall(self, value):
        """Transform :class:`str` into an :class:`object` instance.

        :param str value: the UTF-8 representation of an object
        :return: the decoded :class:`object` representation

        """
        data = parse.parse_qs(value)
        for key, value in data.items():
            if isinstance(value, list) and len(value) == 1:
                data[key] = value.pop()
        return data


def normalize(value):
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
    elif isinstance(value, bytearray):
        return bytes(value)
    elif isinstance(value, memoryview):
        return value.tobytes()
    elif hasattr(value, 'isoformat'):
        return value.isoformat()
    elif isinstance(value, bytes) or isinstance(value, str):
        return value
    elif isinstance(value, (collections.Sequence, collections.Set)):
        return [normalize(item) for item in value]
    elif isinstance(value, collections.Mapping):
        return dict((k, normalize(v)) for k, v in value.items())
    raise TypeError('{} is not supported'.format(value.__class__.__name__))
