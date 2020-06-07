"""Common Encoding Methods"""


def to_str(value, encoding):
    """Decode a :obj:`bytes` object into a str with UTF-8 encoding.

    :param bytes value: The value to decode
    :param str encoding: The encoding type to use
    :rtype: str

    """
    return value.decode(encoding)


def recursive_to_str(value, encoding):
    """Recursively convert bytes to strings.

    Ensure that any bytes objects are converted to strings. This includes
    keys and values in dicts, and all values in a list or tuple.

    :param mixed value: The value to process
    :param str encoding: The encoding type to use
    :rtype: mixed

    """
    if isinstance(value, dict):
        return {to_str(k, encoding): recursive_to_str(v, encoding)
                for k, v in value.items()}
    elif isinstance(value, list):
        return [recursive_to_str(v, encoding) for v in value]
    elif isinstance(value, tuple):
        return tuple(recursive_to_str(v, encoding) for v in value)
    elif isinstance(value, bytes):
        return to_str(value, encoding)
    return value
