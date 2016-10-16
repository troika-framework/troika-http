import base64
import datetime
import os
import struct
import sys
import unittest
import uuid

from troika.http import transcoders


class UTC(datetime.tzinfo):
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def dst(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return 'UTC'


class Context(object):
    """Super simple class to call setattr on"""
    def __init__(self):
        self.settings = {}


def pack_string(obj):
    """Optimally pack a string according to msgpack format"""
    payload = str(obj).encode('ASCII')
    l = len(payload)
    if l < (2 ** 5):
        prefix = struct.pack('B', 0b10100000 | l)
    elif l < (2 ** 8):
        prefix = struct.pack('BB', 0xD9, l)
    elif l < (2 ** 16):
        prefix = struct.pack('>BH', 0xDA, l)
    else:
        prefix = struct.pack('>BI', 0xDB, l)
    return prefix + payload


def pack_bytes(payload):
    """Optimally pack a byte string according to msgpack format"""
    l = len(payload)
    if l < (2 ** 8):
        prefix = struct.pack('BB', 0xC4, l)
    elif l < (2 ** 16):
        prefix = struct.pack('>BH', 0xC5, l)
    else:
        prefix = struct.pack('>BI', 0xC6, l)
    return prefix + payload


class JSONTests(unittest.TestCase):

    def setUp(self):
        super(JSONTests, self).setUp()
        self.transcoder = transcoders.JSON()

    def test_that_uuids_are_dumped_as_strings(self):
        obj = {'id': uuid.uuid4()}
        dumped = self.transcoder._marshall(obj)
        self.assertEqual(dumped.replace(' ', ''), '{"id":"%s"}' % obj['id'])

    def test_that_datetimes_are_dumped_in_isoformat(self):
        obj = {'now': datetime.datetime.now()}
        dumped = self.transcoder._marshall(obj)
        self.assertEqual(dumped.replace(' ', ''),
                         '{"now":"%s"}' % obj['now'].isoformat())

    def test_that_tzaware_datetimes_include_tzoffset(self):
        obj = {'now': datetime.datetime.now().replace(tzinfo=UTC())}
        self.assertTrue(obj['now'].isoformat().endswith('+00:00'))
        dumped = self.transcoder._marshall(obj)
        self.assertEqual(dumped.replace(' ', ''),
                         '{"now":"%s"}' % obj['now'].isoformat())

    @unittest.skipIf(sys.version_info[0] == 2, 'bytes unsupported on python 2')
    def test_that_bytes_are_base64_encoded(self):
        bin = bytes(os.urandom(127))
        dumped = self.transcoder._marshall({'bin': bin})
        self.assertEqual(
            dumped, '{"bin":"%s"}' % base64.b64encode(bin).decode('ASCII'))

    def test_that_bytearrays_are_base64_encoded(self):
        bin = bytearray(os.urandom(127))
        dumped = self.transcoder._marshall({'bin': bin})
        self.assertEqual(
            dumped, '{"bin":"%s"}' % base64.b64encode(bin).decode('ASCII'))

    def test_that_memoryviews_are_base64_encoded(self):
        bin = memoryview(os.urandom(127))
        dumped = self.transcoder._marshall({'bin': bin})
        self.assertEqual(
            dumped, '{"bin":"%s"}' % base64.b64encode(bin).decode('ASCII'))

    def test_that_unhandled_objects_raise_type_error(self):
        with self.assertRaises(TypeError):
            self.transcoder.to_bytes(object())


class MessagePackTests(unittest.TestCase):

    def setUp(self):
        super(MessagePackTests, self).setUp()
        self.transcoder = transcoders.MessagePack()

    def test_that_strings_are_dumped_as_strings(self):
        dumped = self.transcoder._marshall(u'foo')
        self.assertEqual(self.transcoder._unmarshall(dumped), 'foo')
        self.assertEqual(dumped, pack_string('foo'))

    def test_that_none_is_packed_as_nil_byte(self):
        self.assertEqual(self.transcoder._marshall(None), b'\xC0')

    def test_that_bools_are_dumped_appropriately(self):
        self.assertEqual(self.transcoder._marshall(False), b'\xC2')
        self.assertEqual(self.transcoder._marshall(True), b'\xC3')

    def test_that_ints_are_packed_appropriately(self):
        self.assertEqual(self.transcoder._marshall((2 ** 7) - 1), b'\x7F')
        self.assertEqual(self.transcoder._marshall(2 ** 7), b'\xCC\x80')
        self.assertEqual(self.transcoder._marshall(2 ** 8), b'\xCD\x01\x00')
        self.assertEqual(self.transcoder._marshall(2 ** 16),
                         b'\xCE\x00\x01\x00\x00')
        self.assertEqual(self.transcoder._marshall(2 ** 32),
                         b'\xCF\x00\x00\x00\x01\x00\x00\x00\x00')

    def test_that_negative_ints_are_packed_accordingly(self):
        self.assertEqual(self.transcoder._marshall(-(2 ** 0)), b'\xFF')
        self.assertEqual(self.transcoder._marshall(-(2 ** 5)), b'\xE0')
        self.assertEqual(self.transcoder._marshall(-(2 ** 7)), b'\xD0\x80')
        self.assertEqual(self.transcoder._marshall(-(2 ** 15)),
                         b'\xD1\x80\x00')
        self.assertEqual(self.transcoder._marshall(-(2 ** 31)),
                         b'\xD2\x80\x00\x00\x00')
        self.assertEqual(self.transcoder._marshall(-(2 ** 63)),
                         b'\xD3\x80\x00\x00\x00\x00\x00\x00\x00')

    def test_that_lists_are_treated_as_arrays(self):
        dumped = self.transcoder._marshall(list())
        self.assertEqual(self.transcoder._unmarshall(dumped), [])
        self.assertEqual(dumped, b'\x90')

    def test_that_tuples_are_treated_as_arrays(self):
        dumped = self.transcoder._marshall(tuple())
        self.assertEqual(self.transcoder._unmarshall(dumped), [])
        self.assertEqual(dumped, b'\x90')

    def test_that_sets_are_treated_as_arrays(self):
        dumped = self.transcoder._marshall(set())
        self.assertEqual(self.transcoder._unmarshall(dumped), [])
        self.assertEqual(dumped, b'\x90')

    def test_that_unhandled_objects_raise_type_error(self):
        with self.assertRaises(TypeError):
            self.transcoder._marshall(object())

    def test_that_uuids_are_dumped_as_strings(self):
        uid = uuid.uuid4()
        dumped = self.transcoder._marshall(uid)
        self.assertEqual(self.transcoder._unmarshall(dumped), str(uid))
        self.assertEqual(dumped, pack_string(uid))

    def test_that_datetimes_are_dumped_in_isoformat(self):
        now = datetime.datetime.now()
        dumped = self.transcoder._marshall(now)
        self.assertEqual(self.transcoder._unmarshall(dumped), now.isoformat())
        self.assertEqual(dumped, pack_string(now.isoformat()))

    def test_that_tzaware_datetimes_include_tzoffset(self):
        now = datetime.datetime.now().replace(tzinfo=UTC())
        self.assertTrue(now.isoformat().endswith('+00:00'))
        dumped = self.transcoder._marshall(now)
        self.assertEqual(self.transcoder._unmarshall(dumped), now.isoformat())
        self.assertEqual(dumped, pack_string(now.isoformat()))

    def test_that_bytes_are_sent_as_bytes(self):
        data = bytes(os.urandom(127))
        dumped = self.transcoder._marshall(data)
        self.assertEqual(self.transcoder._unmarshall(dumped), data)
        self.assertEqual(dumped, pack_bytes(data))

    def test_that_bytearrays_are_sent_as_bytes(self):
        data = bytearray(os.urandom(127))
        dumped = self.transcoder._marshall(data)
        self.assertEqual(self.transcoder._unmarshall(dumped), data)
        self.assertEqual(dumped, pack_bytes(data))

    def test_that_memoryviews_are_sent_as_bytes(self):
        data = memoryview(os.urandom(127))
        dumped = self.transcoder._marshall(data)
        self.assertEqual(self.transcoder._unmarshall(dumped), data)
        self.assertEqual(dumped, pack_bytes(data.tobytes()))

    def test_that_utf8_values_can_be_forced_to_bytes(self):
        data = b'a ascii value'
        dumped = self.transcoder._marshall(data)
        self.assertEqual(self.transcoder._unmarshall(dumped), data)
        self.assertEqual(dumped, pack_bytes(data))
