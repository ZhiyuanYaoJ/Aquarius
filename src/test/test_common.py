# Copyright(c) 2021 Cisco and / or its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http: // www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''
This file conducts unit-test on src/utils/common.py
'''
import os
import sys
import json
import shutil
import unittest
DIRNAME = os.path.dirname(__file__)
UTILS_DIR = '{}/../utils'.format(DIRNAME)
ROOT_DIR = os.path.join(DIRNAME, '..', '..')
TMP_DIR = os.path.join(ROOT_DIR, 'data', 'tmp')
sys.path.insert(0, UTILS_DIR)
import common

class TestUtils(unittest.TestCase):
    '''
    This class tests the src/utils/common.py
    '''

    def test_write_file(self):
        '''
        @brief: test if the file can be written
        '''
        file2test = os.path.join(TMP_DIR, "unittest.log")
        string2write = "unit test is ok?"
        if os.path.exists(file2test):
            os.remove(file2test)
        common.write_file([string2write]*3, file2test)
        self.assertTrue(os.path.exists(file2test))
        with open(file2test, "r") as myfile:
            lines = [line.rstrip('\n') for line in myfile]
        self.assertEqual(len(lines), 3)
        for l_current in lines:
            self.assertEqual(l_current, string2write)
        os.remove(file2test)

    def test_read_file(self):
        '''
        @brief: test if file can be read
        '''
        file2test = os.path.join(TMP_DIR, "unittest.log")
        string2write = "unit test is ok?"
        if os.path.exists(file2test):
            os.remove(file2test)
        common.write_file([string2write]*3, file2test)
        lines = common.read_file(file2test)
        self.assertEqual(len(lines), 3)
        for l_current in lines:
            self.assertEqual(l_current, string2write)
        os.remove(file2test)

    def test_init_logger(self):
        '''
        @brief: test if logger is initialized
        '''
        file2test = os.path.join(TMP_DIR, "unittest.log")
        string2write = "unit test is ok?"
        if os.path.exists(file2test):
            os.remove(file2test)
        test_logger = common.init_logger(file2test, "test_logger")
        test_logger.info(string2write)
        lines = common.read_file(file2test)
        self.assertTrue(string2write in lines[-1])
        os.remove(file2test)


    def test_json_write2file(self):
        '''
        @brief: test if dictionary can be written into files
        '''
        test_dict = {"a": 1, "b": 2, "c": 3}
        file2test = os.path.join(TMP_DIR, "unittest.json")
        if os.path.exists(file2test):
            os.remove(file2test)
        common.json_write2file(test_dict, file2test)
        self.assertTrue(os.path.exists(file2test))
        with open(file2test, 'r') as read_file:
            verify_dict = json.load(read_file)
        self.assertDictEqual(verify_dict, test_dict)
        os.remove(file2test)


    def test_json_read_file(self):
        '''
        @brief: test if dictionary can be read from json files
        '''
        test_dict = {"a": 1, "b": 2, "c": 3}
        file2test = os.path.join(TMP_DIR, "unittest.json")
        if os.path.exists(file2test):
            os.remove(file2test)
        common.json_write2file(test_dict, file2test)
        verify_dict = common.json_read_file(file2test)
        self.assertDictEqual(verify_dict, test_dict)
        os.remove(file2test)

    def test_create_folder(self):
        '''
        @brief: test if folder can be created
        '''
        folders2test = [os.path.join(TMP_DIR, "unittest")]
        folders2test.append(os.path.join(folders2test[-1], "testunit"))
        if os.path.exists(folders2test[0]):
            shutil.rmtree(folders2test[0])
        common.create_folder(folders2test)
        self.assertTrue(os.path.exists(folders2test[-1]))
        shutil.rmtree(folders2test[0])
