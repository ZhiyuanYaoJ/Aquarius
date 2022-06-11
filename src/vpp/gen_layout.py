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

import sys
import os
import argparse
# add common utils to path
DIRNAME = os.path.dirname(__file__)
UTILS_DIR = os.path.join(DIRNAME, '../utils')
sys.path.insert(0, UTILS_DIR)
import common

PARSER = argparse.ArgumentParser(description=
                                 'Generate shared memory layout header for LB plugin in VPP.')

PARSER.add_argument('-m', action='store',
                    default='maglev',
                    type=str,
                    dest='method',
                    help='Load Balancing Method')

PARSER.add_argument('--version', action='version',
                    version='%(prog)s 1.0')

#--- utils ---#

def get_line(var_, config, diff=True):
    '''
    @brief:
        put all attributes into one line in the header file
    @param:
        diff: if True then add "_" for array fields
    '''
    res = ""
    if not isinstance(var_[2], int):
        var_[2] = config['global'][var_[2]]
        if diff:
            if var_[2] > 1:
                res += "_"
    if var_[0] not in GLOBAL_CONFIG["map"]["ctype2byte"].keys():
        var_[0] += "_t"
    return res+"_({}, {}, {}, \"{}\", {}) ".format(*var)

#--- macro ---#


#--- main ---#

if __name__ == '__main__':

    ARGS = PARSER.parse_args()

    LAYOUT_FILENAME = os.path.join(
        common.COMMON_CONF['dir']['root'],
        'src',
        'lb',
        common.LB_METHODS[ARGS.method]['version'],
        'shm_layout.json')
    GLOBAL_CONFIG = common.json_read_file(LAYOUT_FILENAME)

    # for different methods, add different macros
    assert ARGS.method in common.LB_METHODS.keys()
    lines = common.LB_METHODS[ARGS.method]['vpp_macro']
    lines.append("")

    for k, v in GLOBAL_CONFIG["global"].items():
        if "_FMT" in k:
            continue # skip format strings
        lines.append("#define {} {}".format(k, v))
    lines.append("")

    for k, value_ in GLOBAL_CONFIG["vpp"]["struct"].items():
        lines.append("#define lb_foreach_{} \\".format(k))
        for var in value_:
            lines.append(get_line(var, GLOBAL_CONFIG))
            if var != value_[-1]:
                lines[-1] += "\\"
        lines.append("")

    lines.append("#define lb_foreach_typedef_struct \\")
    for k, value_ in GLOBAL_CONFIG["vpp"]["struct"].items():
        lines.append("_construct({}) \\".format(k))
    lines.append("")

    for k, value_ in GLOBAL_CONFIG["vpp"]["enum"].items():
        lines.append("#define lb_foreach_{} \\".format(k))
        for var in value_:
            lines.append("_({}, \"{}\") ".format(*var))
            if var != value_[-1]:
                lines[-1] += "\\"
        lines.append("")

    lines.append("#define lb_foreach_layout \\")
    value_ = GLOBAL_CONFIG["layout"]
    for var in value_:
        lines.append(get_line(var, GLOBAL_CONFIG, diff=False))
        if var != value_[-1]:
            lines[-1] += "\\"
    lines.append("")

    common.write_file(lines, os.path.join(
        common.COMMON_CONF['dir']['root'],
        'src',
        'vpp',
        common.LB_METHODS[ARGS.method]['version'],
        'lb',
        'shm.h'))
