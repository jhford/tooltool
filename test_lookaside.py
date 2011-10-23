import sys
import os
import unittest
import logging
import shutil
import tempfile
import copy
try: import simplejson as json
except ImportError: import json

# We want access to the module we are testing
sys.path.append('.')
import lookaside
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.sample_data = open('test_file.ogg')
        self.sample_algo = 'sha1'
        self.sample_hash = 'de3e3bbffd83c328ad7d9537ad2d03f68fc02e52'

    def test_hash_file(self):
        test_hash = lookaside.hash_file(self.sample_data, self.sample_algo)
        self.assertEqual(test_hash, self.sample_hash)

#Ugh, I've managed to have a few different test naming schemes already :(
#TODO: clean this up!

class BaseFileRecordTest(unittest.TestCase):
    def setUp(self):
        self.sample_file = 'test_file.ogg'
        self.sample_algo = 'sha1'
        self.sample_size = os.path.getsize(self.sample_file)
        with open(self.sample_file) as f:
            self.sample_hash = lookaside.hash_file(f, self.sample_algo)
        self.test_record = lookaside.FileRecord(
                filename=self.sample_file,
                size=self.sample_size,
                digest=self.sample_hash,
                algorithm=self.sample_algo
        )
        # using mkstemp to ensure that the filename generated
        # isn't actually on the system.
        (tmpfd, filename) = tempfile.mkstemp()
        os.close(tmpfd)
        os.remove(filename)
        if os.path.exists(filename):
            self.fail('did not remove %s' % filename)
        self.absent_file = filename

class BaseFileRecordListTest(BaseFileRecordTest):
    def setUp(self):
        BaseFileRecordTest.setUp(self)
        self.record_list = []
        for i in range(0,4):
            record = copy.deepcopy(self.test_record)
            record.algorithm = i
            self.record_list.append(record)


class TestFileRecord(BaseFileRecordTest):
    def test_present(self):
        # this test feels silly, but things are built on this
        # method, so probably best to test it
        self.assertTrue(self.test_record.present())

    def test_absent(self):
        self.test_record.filename = self.absent_file
        self.assertFalse(self.test_record.present())

    def test_valid_size(self):
        self.assertTrue(self.test_record.validate_size())

    def test_invalid_size(self):
        self.test_record.size += 1
        self.assertFalse(self.test_record.validate_size())

    def test_size_of_missing_file(self):
        self.test_record.filename = self.absent_file
        self.assertRaises(lookaside.MissingFileException,self.test_record.validate_size)

    def test_valid_digest(self):
        self.assertTrue(self.test_record.validate_digest())

    def test_invalid_digest(self):
        self.test_record.digest = 'NotValidDigest'
        self.assertFalse(self.test_record.validate_digest())

    def test_digest_of_missing_file(self):
        self.test_record.filename = self.absent_file
        self.assertRaises(lookaside.MissingFileException,self.test_record.validate_digest)

    def test_overall_valid(self):
        self.assertTrue(self.test_record.validate())

    def test_overall_invalid_size(self):
        self.test_record.size = 3
        self.assertFalse(self.test_record.validate())

    def test_overall_invalid_digest(self):
        self.test_record.digest = 'NotValidDigest'
        self.assertFalse(self.test_record.validate())

    def test_overall_invalid_missing_file(self):
        self.test_record.filename = self.absent_file
        self.assertRaises(lookaside.MissingFileException,self.test_record.validate)

    def test_equality(self):
        test_record2 = copy.deepcopy(self.test_record)
        self.assertEqual(self.test_record, test_record2)
        self.assertEqual(self.test_record, self.test_record)

    def test_inequality(self):
        for i in ['filename', 'size', 'algorithm', 'digest']:
            test_record2 = copy.deepcopy(self.test_record)
            test_record2.i = 'wrong!' # this works, shockingly
            self.assertNotEqual(self.test_record, test_record2)

class TestFileRecordJSONCodecs(BaseFileRecordListTest):
    def test_default(self):
        encoder = lookaside.FileRecordJSONEncoder()
        dict_from_encoder = encoder.default(self.test_record)
        for i in ['filename', 'size', 'algorithm', 'digest']:
            self.assertEqual(dict_from_encoder[i], self.test_record.__dict__[i])

    def test_default_list(self):
        encoder = lookaside.FileRecordJSONEncoder()
        new_list = encoder.default(self.record_list)
        for record in range(0,len(self.record_list)):
            self.assertEqual(new_list[record],
                             encoder.default(self.record_list[record]))

    def test_unrelated_class(self):
        encoder = lookaside.FileRecordJSONEncoder()
        class Junk: pass
        self.assertRaises(
                lookaside.FileRecordJSONEncoderException,
                encoder.default,
                Junk()
        )

    def test_list_with_unrelated_class(self):
        encoder = lookaside.FileRecordJSONEncoder()
        class Junk: pass
        self.assertRaises(
                lookaside.FileRecordJSONEncoderException,
                encoder.default,
                [self.test_record, Junk(), self.test_record],
        )

    def test_decode(self):
        json_string = json.dumps(self.test_record, cls=lookaside.FileRecordJSONEncoder)
        decoder = lookaside.FileRecordJSONDecoder()
        f=decoder.decode(json_string)
        for i in ['filename', 'size', 'algorithm', 'digest']:
            self.assertEqual(getattr(f,i), self.test_record.__dict__[i])

    def test_json_dumps(self):
        json_string = json.dumps(self.test_record, cls=lookaside.FileRecordJSONEncoder)
        dict_from_json = json.loads(json_string)
        for i in ['filename', 'size', 'algorithm', 'digest']:
            self.assertEqual(dict_from_json[i], self.test_record.__dict__[i])

    def test_decode_list(self):
        json_string = json.dumps(self.record_list, cls=lookaside.FileRecordJSONEncoder)
        new_list = json.loads(json_string, cls=lookaside.FileRecordJSONDecoder)
        self.assertEquals(len(new_list), len(self.record_list))
        for record in range(0,len(self.record_list)):
            self.assertEqual(new_list[record], self.record_list[record])



class TestAsideFile(BaseFileRecordTest):
    def setUp(self):
        BaseFileRecordTest.setUp(self)
        self.other_sample_file = 'other-%s' % self.sample_file
        if os.path.exists(self.other_sample_file):
            os.remove(self.other_sample_file)
        shutil.copyfile(self.sample_file, self.other_sample_file)
        self.other_test_record = copy.deepcopy(self.test_record)
        self.other_test_record.filename = self.other_sample_file
        self.test_aside = lookaside.AsideFile([self.test_record, self.other_test_record])

    def test_present(self):
        self.assertTrue(self.test_aside.present())

    def test_absent(self):
        os.remove(self.other_sample_file)
        self.assertFalse(self.test_aside.present())

    def test_validate_sizes(self):
        self.assertTrue(self.test_aside.validate_sizes())

    def test_incorrect_size(self):
        self.test_aside.file_records[1].size = 1
        self.assertFalse(self.test_aside.validate_sizes())

    def test_validate_digest(self):
        self.assertTrue(self.test_aside.validate_digests())

    def test_incorrect_digest(self):
        self.test_aside.file_records[1].digest = 'wrong'
        self.assertFalse(self.test_aside.validate_digests())

    def test_equality(self):
        one = lookaside.AsideFile([self.test_record, self.other_test_record])
        self.assertEqual(one,one)
        two = one.copy() #copy.deepcopy(one)
        self.assertEqual(one,two)
        one = lookaside.AsideFile([self.test_record, self.other_test_record])
        two = lookaside.AsideFile([self.test_record, self.other_test_record])
        self.assertEqual(one,two)

    def test_json_file(self):
        tmpaside = tempfile.TemporaryFile()
        self.test_aside.dump(tmpaside, fmt='json')
        tmpaside.seek(0)
        new_aside = lookaside.AsideFile()
        new_aside.load(tmpaside, fmt='json')
        for record in range(0,len(self.test_aside.file_records)):
            self.assertEqual(new_aside.file_records[record], self.test_aside.file_records[record])




log = logging.getLogger(lookaside.__name__)
log.setLevel(logging.ERROR)
log.addHandler(logging.StreamHandler())

unittest.main()