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
This script tests all the scripts run on the VMs
'''

import os
import sys
import json
import unittest
DIRNAME = os.path.dirname(__file__)
CLT_DIR = '{}/../clt'.format(DIRNAME)
ROOT_DIR = '{}/../../'.format(DIRNAME)
sys.path.insert(0, CLT_DIR)  # add utils dir to path
import replay_fork_io

class TestClient(unittest.TestCase):
    '''
    This class tests src/clt/replay_fork_io.py
    '''

    def test_dst_ip(self):
        '''
        @brief: check if the replay destination IP address is
        '''
        with open("{}/config/global_conf.json".format(ROOT_DIR), 'r') as read_file:
            global_conf = json.load(read_file)
        self.assertEqual("[{}]".format(global_conf['net']['as6_vip']), replay_fork_io.ADDR)
