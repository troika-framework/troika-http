"""
Common Encoding Methods

"""


def to_str(value):
    """Decode a :obj:`bytes` object into a str with UTF-8 encoding.

    :param bytes value: The value to decode
    :rtype: str

    """
    if isinstance(value, str):
        return value
    return value.decode('utf-8')


def recursive_to_str(value):
    if isinstance(value, dict):
        return dict((to_str(k), recursive_to_str(v)) for k, v in value.items())
    elif isinstance(value, list):
        return list(recursive_to_str(v) for v in value)
    elif isinstance(value, tuple):
        return tuple(recursive_to_str(v) for v in value)
    elif isinstance(value, bytes):
        return to_str(value)
    return value