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
'''This script conducts unit-test for testbed_utils'''
import os
import sys
import json
import shutil
import unittest
DIRNAME = os.path.dirname(__file__)
UTILS_DIR = '{}/../utils'.format(DIRNAME)
sys.path.insert(0, UTILS_DIR)  # add utils dir to path
import testbed_utils as tu
with open('{}/../../config/global_conf.json'.format(DIRNAME), 'r') as file_:
    COMMON_CONF = json.load(file_)
ROOT_DIR = COMMON_CONF['dir']['root']


class TestUtils(unittest.TestCase):
    '''this class test the testbed_utils module'''

    def test_write2file_tee(self):
        '''
        @brief: check whether contents can be created
        '''
        folder2create = "unittest"
        if os.path.exists(folder2create):
            shutil.rmtree(folder2create)
        file2write = os.path.join(folder2create, "test.txt")
        if os.path.exists(file2write):
            os.remove(file2write)
        # test case 1
        str2write = "testline"
        tu.write2file_tee(str2write, file2write)
        with open(file2write, "r") as myfile:
            lines = [line.rstrip('\n') for line in myfile]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], str2write)
        # test case 2
        tu.write2file_tee(str2write, file2write, attach_mode=True)
        with open(file2write, "r") as myfile:
            lines = [line.rstrip('\n') for line in myfile]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], str2write)
        self.assertEqual(lines[1], str2write)
        # cleanup
        self.assertTrue(os.path.exists(file2write))
        shutil.rmtree(folder2create)

    def test_copy_files(self):
        '''
        @brief: check if files or folders can be copied
        '''
        str2write = "test"
        folder2create = "unittest"
        file2create = os.path.join(folder2create, "unittest.txt")
        folder2copy = "unittest_copy"
        file2copy = os.path.join(folder2copy, "unittest_copy.txt")
        if os.path.exists(folder2create):
            shutil.rmtree(folder2create)
        if os.path.exists(folder2copy):
            shutil.rmtree(folder2copy)
        tu.write2file_tee(str2write, file2create)
        os.mkdir(folder2create)
        # check folder is correctly copied
        tu.copy_files(folder2create, folder2copy, isfolder=True, sudoer=False)
        self.assertTrue(os.path.exists(folder2copy))
        # check file is correctly copied
        tu.copy_files(file2create, file2copy, sudoer=False)
        self.assertTrue(os.path.exists(file2copy))
        with open(file2copy, "r") as myfile:
            lines = [line.rstrip('\n') for line in myfile]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], str2write)
        shutil.rmtree(folder2create)
        shutil.rmtree(folder2copy)

    def test_get_config(self):
        '''
        @brief: check that the configuration file is surely what we expect
        '''
        with open("{}/test_conf.json".format(DIRNAME), 'r') as file_target:
            tu.common.COMMON_CONF = json.load(file_target)
        tu.common.COMMON_CONF["dir"]["root"] = ROOT_DIR

        # check the test configuration exists
        conf_file = os.path.join(
            ROOT_DIR, "config", "cluster", "test_cluster.json")
        self.assertTrue(os.path.isfile(conf_file))

        # check the loaded configuration is the same
        with open(conf_file, 'r') as file_target:
            dict_test = json.load(file_target)
        # fetch tu.CONFIG
        tu.get_config("test_cluster.json")
        self.assertDictEqual(tu.CONFIG, dict_test)

    def test_get_nodes(self):
        '''
        @brief: check nodes can be correctly created
        '''
        # test case 1 - kvmp-2 cluster configuration
        tu.get_config("test_cluster.json")
        filename = os.path.join(ROOT_DIR, 'config/lb-methods.json')
        with open(filename, 'r') as file_target:
            lb_methods = json.load(file_target)
        for k, _ in lb_methods.items():
            nodes = tu.get_nodes(k)
            # check # of nodes
            self.assertEqual(
                len(nodes['clt']), tu.CONFIG["global"]["topo"]["n_node"]["clt"])
            self.assertEqual(
                len(nodes['er']), tu.CONFIG["global"]["topo"]["n_node"]["er"])
            self.assertEqual(len(nodes['lb']), 0)
            self.assertEqual(len(nodes['as']), 0)
            for node in nodes['clt']:
                self.assertIsInstance(node, tu.cltNode)
            for node in nodes['er']:
                self.assertIsInstance(node, tu.erNode)

        # test case 2 - kvmp-3 cluster configuration
        tu.get_config("test_cluster_duo.json")
        filename = os.path.join(ROOT_DIR, 'config/lb-methods.json')
        with open(filename, 'r') as file_target:
            lb_methods = json.load(file_target)
        for k, _ in lb_methods.items():
            nodes = tu.get_nodes(k)
            # check # of nodes
            self.assertEqual(len(nodes['clt']), 0)
            self.assertEqual(len(nodes['er']), 0)
            self.assertEqual(
                len(nodes['lb']), tu.CONFIG["global"]["topo"]["n_node"]["lb"])
            self.assertEqual(
                len(nodes['as']), tu.CONFIG["global"]["topo"]["n_node"]["as"])
            for node in nodes['lb']:
                self.assertIsInstance(node, tu.lbNode)
            for node in nodes['as']:
                self.assertIsInstance(node, tu.asNode)

    def test_get_task_name_dir(self):
        '''
        @brief: check that the task name and directory can be correctly generated
        '''
        experiment = "unittest"
        trace = "wiki"
        lb_method = "aqualb"
        sample = "hour0.csv"
        alias = "testunit"
        # test case 1
        task_name, task_dir = tu.get_task_name_dir(
            experiment, trace, lb_method, sample)
        self.assertEqual(
            task_name, '-'.join([trace, lb_method, sample.replace(".csv", "")]))
        self.assertEqual(task_dir, os.path.join(
            ROOT_DIR, "data", "results", experiment, trace, lb_method, sample.replace(".csv", "")))
        # test case 2
        task_name, task_dir = tu.get_task_name_dir(
            experiment, trace, lb_method, sample, alias)
        self.assertEqual(
            task_name, '-'.join([trace, lb_method, sample.replace(".csv", ""), alias]))
        self.assertEqual(
            task_dir,
            os.path.join(
                ROOT_DIR,
                "data",
                "results",
                experiment,
                trace,
                lb_method,
                sample.replace(".csv", "")+"-{}".format(alias)))

    def test_init_task_info(self):
        '''
        @brief: check whether corresponding folders can be created,
                shared memory layout is correctly loaded
        '''
        # define test case variables
        experiment = "unittest"
        trace = "wiki"
        sample = "hour0.csv"
        cluster_config = "test_cluster.json"
        alias = "testunit"
        # initialize configuration
        tu.get_config("test_cluster_duo.json")
        # load methods
        filename = os.path.join(ROOT_DIR, "config/lb-methods.json")
        with open(filename, 'r') as file_target:
            lb_methods = json.load(file_target)
        experiment_dir = os.path.join(ROOT_DIR, "data", "results", experiment)
        for lb_method in lb_methods.keys():
            if os.path.exists(experiment_dir):
                shutil.rmtree(experiment_dir)
            # w/o alias
            shm_file = os.path.join(
                ROOT_DIR, 'src', 'lb', tu.common.LB_METHODS[lb_method]['version'], 'shm_layout.json')
            if os.path.exists(shm_file):
                os.remove(shm_file)
            task_name, task_dir, nodes = tu.init_task_info(
                experiment, lb_method, trace, sample, cluster_config)
            self.assertEqual(lb_method, tu.LB_METHOD)
            self.assertEqual(
                task_name, '-'.join([trace, lb_method, sample.replace(".csv", "")]))
            self.assertEqual(task_dir, os.path.join(
                ROOT_DIR,
                "data",
                "results",
                experiment,
                trace,
                lb_method,
                sample.replace(".csv", "")))
            self.assertTrue(os.path.exists(task_dir))
            self.assertTrue(nodes, tu.get_nodes(lb_method))
            self.assertTrue(os.path.exists(shm_file))
            with open(shm_file, 'r') as file_target:
                shm_layout = json.load(file_target)
            self.assertEqual(shm_layout['meta']['n_as'],
                             tu.CONFIG['global']['topo']['n_node']['as'])
            self.assertEqual(
                shm_layout['meta']['weights'], tu.CONFIG['global']['topo']['n_vcpu']['as'])
            os.remove(shm_file)

            # w/ alias
            shm_file = os.path.join(
                DIRNAME, '../lb', tu.common.LB_METHODS[lb_method]['version'], 'shm_layout.json')
            if os.path.exists(shm_file):
                os.remove(shm_file)
            task_name, task_dir, nodes = tu.init_task_info(
                experiment, lb_method, trace, sample, cluster_config, alias)
            self.assertEqual(lb_method, tu.LB_METHOD)
            self.assertEqual(
                task_name, '-'.join([trace, lb_method, sample.replace(".csv", ""), alias]))
            self.assertEqual(task_dir, os.path.join(
                ROOT_DIR,
                "data",
                "results",
                experiment,
                trace,
                lb_method,
                sample.replace(".csv", "")+"-{}".format(alias)))
            self.assertTrue(os.path.exists(task_dir))
            self.assertTrue(nodes, tu.get_nodes(lb_method))
            self.assertTrue(os.path.exists(shm_file))
            with open(shm_file, 'r') as file_target:
                shm_layout = json.load(file_target)
            self.assertEqual(shm_layout['meta']['n_as'],
                             tu.CONFIG['global']['topo']['n_node']['as'])
            self.assertEqual(
                shm_layout['meta']['weights'], tu.CONFIG['global']['topo']['n_vcpu']['as'])
            os.remove(shm_file)
            shutil.rmtree(experiment_dir)


if __name__ == '__main__':
    unittest.main()
