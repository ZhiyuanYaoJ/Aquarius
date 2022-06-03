#!/usr/bin/python3
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
import os
import subprocess
import json

def json_write2file(data, filename):
    '''
    @brief:
        write data to json file
    '''
    with open(filename, "w") as write_file:
        # w/ indent the file looks better
        json.dump(data, write_file, indent=4)

def json_read_file(filename):
    '''
    @brief:
        read data from json file
    '''
    with open(filename, "r") as read_file:
        return json.load(read_file)

def subprocess_cmd(command, stdout=True):
    '''
    execute command and print out result
    '''
    if stdout:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        return proc_stdout.decode("utf-8")
    else:
        process = subprocess.Popen(command, shell=True)

print("updating global_conf ...\r")
# update root_dir in global_conf
global_conf_file = os.path.join('config', 'global_conf.json')
global_conf = json_read_file(global_conf_file)
global_conf['dir']['root'] = os.getcwd()
# by default, we use the last interface as the vlan interface
global_conf['net']['vlan_if'] = os.listdir('/sys/class/net/')[-1]
hostname = subprocess_cmd("hostname -I").split(' ')[0]
global_conf['net']['base_ip'] = hostname
# by default, we set the server ip indexed by 1 as the local machine
global_conf['net']['physical_server_ip'][1] = hostname
json_write2file(global_conf, global_conf_file)
print("updating global_conf done!")

print("updating unittest-1.json ...\r")
# update unittest-1.json
unittest_file = os.path.join('config', 'cluster', 'unittest-1.json')
cluster_conf = json_read_file(unittest_file)
origin_root_dir = cluster_conf['global']['path']['root']
print("global_conf['dir']['root']=", global_conf['dir']['root'])
for k in cluster_conf['global']['path'].keys():
    cluster_conf['global']['path'][k] = cluster_conf['global']['path'][k].replace(
        origin_root_dir, global_conf['dir']['root'])
cluster_conf['global']['net']['vlan_if'] = os.listdir('/sys/class/net/')[-1]
cluster_conf['global']['net']['base_ip'] = hostname
cluster_conf['global']['net']['physical_server_ip'][1] = hostname
for k, v in cluster_conf['nodes'].items():
    for i in range(len(v)):
        cluster_conf['nodes'][k][i]["physical_server_ip"] = hostname
        cluster_conf['nodes'][k][i]["img"] = cluster_conf['nodes'][k][i]["img"].replace(origin_root_dir, global_conf['dir']['root'])
json_write2file(cluster_conf, unittest_file)
print("updating unittest-1.json done!")
