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
This script tests whether the vpp source code could build successfully
'''
import os
import sys
import unittest
DIRNAME = os.path.dirname(__file__)
UTILS_DIR = '{}/../utils'.format(DIRNAME)
ROOT_DIR = os.path.join(DIRNAME, '..', '..')
TMP_DIR = os.path.join(ROOT_DIR, 'data', 'tmp')
VPP_DIR = os.path.join(ROOT_DIR, 'src', 'vpp', 'base')
sys.path.insert(0, UTILS_DIR)
import testbed_utils as tu


def build_vpp(vpp_dir):
    '''
    build vpp deb files
    '''
    assert os.path.exists('{}/Makefile'.format(vpp_dir)
                          ), "VPP not yet pulled from git submodule, call setup.sh first."
    # first try build once to check if there's an error
    cmd = "#!/bin/bash\n\
cd {}\n\
make build".format(vpp_dir)

    filename = os.path.join(TMP_DIR, "build_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)
    res = tu.subprocess_cmd("bash {}".format(filename))
    return "Error" not in res


class TestVPP(unittest.TestCase):
    '''this class test vpp build'''

    def test_build_vpp(self):
        '''
        @brief: test if no error is thrown when building vpp for all methods
        '''

        cmd = "#!/bin/bash\n\
        cd {}/src/vpp/base\n\
        git submodule init\n\
        git submodule update\n\
        make wipe\n\
        make install-dep\n\
        ".format(ROOT_DIR)

        filename_ = os.path.join(TMP_DIR, "setup.sh")
        with open(filename_, "w") as text_file:
            text_file.write(cmd)
        tu.subprocess_cmd("bash {}".format(filename_))

        # cleanup
        tu.subprocess_cmd("rm -f {}".format(filename_))


        filename_ = os.path.join(ROOT_DIR, 'config', 'lb-methods.json')
        lb_methods = tu.common.json_read_file(filename_)
        for method in lb_methods.keys():
            cmd = 'cp -r {} {}/src/plugins/'.format(
                os.path.join(ROOT_DIR, 'src', 'vpp', lb_methods[method]['version'], 'lb'), VPP_DIR)
            tu.subprocess_cmd(cmd)
            self.assertTrue(build_vpp(VPP_DIR))
            print("Method {} built in version {} succeeded!".format(
                method, lb_methods[method]['version']))
