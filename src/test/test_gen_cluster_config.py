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
This file conducts unit-test on src/utils/gen_cluster_config.py
'''
import os
import sys
import unittest
DIRNAME = os.path.dirname(__file__)
UTILS_DIR = '{}/../utils'.format(DIRNAME)
ROOT_DIR = os.path.join(DIRNAME, '..', '..')
TMP_DIR = os.path.join(ROOT_DIR, 'data', 'tmp')
sys.path.insert(0, UTILS_DIR)
import gen_cluster_config as gcc


class TestGCC(unittest.TestCase):
    '''
    @brief: This class tests the src/utils/gen_cluster_config.py
    '''

    def test_generate_l2_addr(self):
        '''
        @brief: check if the randomly generated layer-2 address is valid
        '''
        l2addr = gcc.generate_l2_addr()
        cnt_field = 0
        for i, field_ in enumerate(l2addr.split(':')):
            self.assertTrue(int(field_, 16) < 256)
            self.assertTrue(int(field_, 16) >= 0)
            cnt_field = i
        self.assertEqual(cnt_field, 5)

    def test_path_config(self):
        '''
        @brief: test path configuration is correctly instantiated
        '''
        path_config = gcc.PathConfig(TMP_DIR)
        self.assertEqual(path_config.root, TMP_DIR)
        self.assertEqual(path_config.config, os.path.join(
            TMP_DIR, 'config'))
        self.assertEqual(path_config.src, os.path.join(
            TMP_DIR, 'src'))
        self.assertEqual(path_config.vpp, os.path.join(
            TMP_DIR, 'data', 'vpp_deb'))
        self.assertEqual(path_config.img, os.path.join(
            TMP_DIR, 'data', 'img'))
        self.assertEqual(path_config.tmp, os.path.join(
            TMP_DIR, 'data', 'tmp'))
        self.assertEqual(path_config.trace, os.path.join(
            TMP_DIR, 'data', 'trace'))
        self.assertEqual(path_config.orig_img, os.path.join(
            path_config.img, 'origin', 'lb-vpp.img'))
        self.assertEqual(path_config.base_img, os.path.join(
            path_config.img, 'lb-vpp-base.img'))

    def test_topo_config(self):
        '''
        @brief: test topology configuration is correctly instantiated
        '''
        # normal case
        test_config = {
            'n_node': {
                'clt': 1,
                'er': 1,
                'lb': 1,
                'as': 4,
            },
            'n_vcpu': {
                'clt': [4],
                'er': [2],
                'lb': [2],
                'as': [2]*4,
            },
            'physical_server_id': {
                'clt': [1],
                'er': [1],
                'lb': [1],
                'as': [1]*4,
            },
            'thread_per_cpu': 2,
            'n_cpu': 24,
            'n_server': 4,
        }
        topo_config_verify = gcc.TopoConfig(**test_config)
        self.assertDictEqual(
            topo_config_verify.__dict__,
            {
                "n_node": {
                    "clt": 1,
                    "er": 1,
                    "lb": 1,
                    "as": 4
                },
                "n_vcpu": {
                    "clt": [
                        4
                    ],
                    "er": [
                        2
                    ],
                    "lb": [
                        2
                    ],
                    "as": [
                        2,
                        2,
                        2,
                        2
                    ]
                },
                "physical_server_id": {
                    "clt": [
                        1
                    ],
                    "er": [
                        1
                    ],
                    "lb": [
                        1
                    ],
                    "as": [
                        1,
                        1,
                        1,
                        1
                    ]
                },
                "thread_per_cpu": 2,
                "n_cpu": 24,
                "n_server": 4,
                "vcpu_list": {
                    "clt": [
                        [
                            0,
                            24,
                            1,
                            25,
                            2,
                            26,
                            3,
                            27
                        ]
                    ],
                    "er": [
                        [
                            4,
                            28,
                            5,
                            29
                        ]
                    ],
                    "lb": [
                        [
                            6,
                            30,
                            7,
                            31
                        ]
                    ],
                    "as": [
                        [
                            8,
                            32,
                            9,
                            33
                        ],
                        [
                            10,
                            34,
                            11,
                            35
                        ],
                        [
                            12,
                            36,
                            13,
                            37
                        ],
                        [
                            14,
                            38,
                            15,
                            39
                        ]
                    ]
                }
            }
        )
        # asserted case
        test_config = {
            'n_node': {
                'clt': 1,
                'er': 1,
                'lb': 1,
                'as': 44,
            },
            'n_vcpu': {
                'clt': [4],
                'er': [2],
                'lb': [2],
                'as': [2]*44,
            },
            'physical_server_id': {
                'clt': [1],
                'er': [1],
                'lb': [1],
                'as': [1]*44,
            },
            'thread_per_cpu': 2,
            'n_cpu': 24,
            'n_server': 4,
        }
        self.assertRaises(ValueError, gcc.TopoConfig, **test_config)

#
