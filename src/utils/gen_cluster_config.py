#!/usr/bin/env python
# coding: utf-8
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
# %%==================================================
'''
import dependencies
'''
from random import randint
import os
import common

# %%==================================================
# macro & global variables

NODE_TYPES = ['clt', 'er', 'lb', 'as']


# %%==================================================
# lower-level functions

def generate_l2_addr():
    '''
    @brief:
        randomly generate l2 address
    '''
    return "de:ad:ca:fe:{:02x}:{:02x}".format(randint(0, 255), randint(0, 255))


# %%==================================================
# class

class IP4Range:
    def __get__(self, instance, owner):
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        if value < 0 or value >= 254:
            raise ValueError('Does not fit ip4 suffix format (range [0-254)).')
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name


class PathConfig(object):

    def __init__(self,
                 root_dir,  # root directory
                 ):
        self.root = root_dir
        self.config = os.path.join(self.root, 'config')
        self.src = os.path.join(self.root, 'src')
        data_dir = os.path.join(self.root, 'data')
        # store vpp deb files and plugin files
        self.vpp = os.path.join(data_dir, 'vpp_deb')
        self.img = os.path.join(data_dir, 'img')  # store image files
        self.tmp = os.path.join(data_dir, 'tmp')  # tmp folder
        self.trace = os.path.join(data_dir, 'trace')  # wiki replay folder
        # original image file
        self.orig_img = os.path.join(self.img, 'origin', 'lb-vpp.img')
        self.base_img = os.path.join(self.img, 'lb-vpp-base.img')  # base image file


class TopoConfig(object):

    def __init__(
            self,
            n_node={
                'clt': 1,
                'er': 1,
                'lb': 1,
                'as': 4,
            },
            n_vcpu={
                'clt': [4],
                'er': [2],
                'lb': [2],
                'as': [2]*2+[4]*2,
            },
            physical_server_id={
                'clt': [1],
                'er': [1],
                'lb': [1],
                'as': [1]*4,
            },
            thread_per_cpu=2,
            n_cpu=24,
            n_server=4,
        ):
        self.__dict__.update(
            {k: v for k, v in locals().items() if k != 'self'})

        next_thread_available = []
        for i in range(n_server):
            next_thread_available.append(0)

        thread_priority_list = []
        for i in range(n_cpu):
            for ii in range(thread_per_cpu):
                thread_priority_list.append(i+ii*n_cpu)

        self.vcpu_list = {}
        for key in NODE_TYPES:
            self.vcpu_list[key] = []
            for i in range(n_node[key]):
                sid = physical_server_id[key][i]
                n_vcpu_node = n_vcpu[key][i]
                n_thread = int(n_vcpu_node * thread_per_cpu)
                if next_thread_available[sid]+n_thread > n_cpu * thread_per_cpu:
                    raise ValueError('Server threads not sufficient for so many nodes.' +
                                     "(server {}, vcpu_list[{}]={})".format(
                                         sid, key, self.vcpu_list))
                vcpu_list = thread_priority_list[
                    next_thread_available[sid]:next_thread_available[sid]+n_thread]
                self.vcpu_list[key].append(vcpu_list)

                next_thread_available[sid] += n_thread
                next_thread_available[sid] = int(
                    (next_thread_available[sid]+1)/thread_per_cpu)*thread_per_cpu


class NetConfig(object):

    def __init__(self,
                 as4_vip,      # server vip v4 addr
                 as6_vip,      # server vip v6 addr
                 lb4_vip_fmt,  # lb vip v4 addr format
                 lb6_vip_fmt,  # lb vip v6 addr format
                 br4_fmt,      # bridge ip v4 format
                 br6_fmt,      # bridge ip v6 format
                 tap4_fmt,     # tap interface ip v4 format
                 tap6_fmt,     # tap interface ip v6 format
                 clt4_fmt,     # client interface ip v4 format
                 clt6_fmt,     # client interface ip v6 format
                 l2_fmt,       # L2 address format
                 mgmt_fmt,     # management interface ip format
                 lb_mgmt_port,  # lb node management (ssh) port baseline
                 as_mgmt_port,  # server node management (ssh) port baseline
                 # edge router node management (ssh) port baseline
                 er_mgmt_port,
                 clt_mgmt_port,  # client node management (ssh) port baseline
                 bridge,       # name of the bridge that links all lbs and servers
                 mgmt_bridge,  # name of the management bridge that links all lbs and servers
                 vlan_if,  # name of the interface for VLAN
                 vlan_id,  # id of the interface for VLAN
                 vlan_mgmt_id,  # id of the interface for VLAN
                 physical_server_ip,  # ip list of physical server
                 base_ip,  # ip of the base physical server on which results are gathered
                 ):
        self.__dict__.update(
            {k: v for k, v in locals().items() if k != 'self'})


class GlobalConfig(object):

    def __init__(self,
                 root_dir,
                 topo_conf,
                 net_conf,
                 ):
        self.path = PathConfig(root_dir)
        self.topo = TopoConfig(**topo_conf)
        self.net = NetConfig(**net_conf)

    def to_dict(self):
        return {k: v.__dict__ for k, v in self.__dict__.items()}


# %%==================================================
'''
node classes
'''


class NodeConfig(object):
    '''configuration for node'''

    id = IP4Range()

    def __init__(self,
                 id,  # node id
                 node_type,  # type of current node {'lb', 'as', 'er', 'clt'}
                 ssh_port,  # ssh port
                 mgmt_ip,  # eth1 ip
                 isvpp,  # whether this node uses vpp or not
                 hostname,  # hostname of this node
                 tap_list,  # tap interface name list
                 vcpu_list,  # id of cpu mapping
                 l2_list=None,  # l2 addr for the node
                 ip4_list=None,  # node ip v4
                 sn4_list=None,  # node ip v4 subnet (default 24 for all ip)
                 ip6_list=None,  # node ip v6
                 sn6_list=None,  # node ip v6 subnet (default 64 for all ip)
                 physical_server_id=0,  # id of the physical server
                 ):
        # check variable
        if ip4_list:
            if not isinstance(ip4_list, (list)):
                ip4_list = [ip4_list]
        else:
            ip4_list = []

        if sn4_list:
            if not isinstance(sn4_list, (list)):
                sn4_list = [sn4_list]
            assert len(sn4_list) == len(ip4_list)
        else:
            sn4_list = [24] * len(ip4_list)

        if ip6_list:
            if not isinstance(ip6_list, (list)):
                ip6_list = [ip6_list]
        else:
            ip6_list = []

        if sn6_list:
            if not isinstance(sn6_list, (list)):
                sn6_list = [sn6_list]
            assert len(sn6_list) == len(ip6_list)
        else:
            sn6_list = [64] * len(ip6_list)

        if l2_list:
            if not isinstance(l2_list, (list)):
                l2_list = [l2_list]
        else:
            l2_list = []
        l2_list = [generate_l2_addr()] + l2_list

        if not isinstance(tap_list, (list)):
            tap_list = [tap_list]

        self.__dict__.update(
            {k: v for k, v in locals().items() if k != 'self'})
        self.img = os.path.join(GLOBAL_CONF.path.img, self.hostname + '.img')

        self.physical_server_ip = GLOBAL_CONF.net.physical_server_ip[physical_server_id]

        assert len(self.tap_list) == len(
            self.l2_list), 'Number of tap interfaces should be equal to number of L2 addresses + 1!'
        assert len(self.tap_list) >= 1, 'At least one tap interface for mgmt'

    def __getitem__(self, key):
        return getattr(self, key)

    def keys(self):
        '''get all the keys'''
        return ('id', 'node_type', 'hostname', 'isvpp', 'ssh_port',
                'mgmt_ip', 'l2_list', 'tap_list', 'ip4_list', 'ip6_list',
                'sn4_list', 'sn6_list', 'img', 'vcpu_list',
                'physical_server_id', 'physical_server_ip')


class LB_Config(NodeConfig):
    '''configuration for load balancers'''

    def __init__(self,
                 lb_id,  # id of this lb node
                 er_list=None,  # list of edge router node ids
                 as_list=None,  # list of server node ids
                 clt_list=None,  # list of client node ids
                 ):
        net_conf = GLOBAL_CONF.net
        if not isinstance(as_list, (list)):
            as_list = list(range(GLOBAL_CONF.topo.n_node['as']))
        self.as_list = as_list
        self.as_ip4_list = [net_conf.tap4_fmt.format(
            i+1) for i in self.as_list]
        self.as_ip6_list = [net_conf.tap6_fmt.format(
            i+1) for i in self.as_list]
        self.gre4_list = [net_conf.lb4_vip_fmt.format(
            i+1) for i in self.as_list]
        self.gre6_list = [net_conf.lb6_vip_fmt.format(
            i+1) for i in self.as_list]
        self.vip4 = net_conf.as4_vip
        self.vip6 = net_conf.as6_vip
        if not isinstance(er_list, (list)):
            er_list = list(range(GLOBAL_CONF.topo.n_node['er']))
        self.er_list = er_list
        self.er_ip4_list = [net_conf.tap4_fmt.format(
            254-i) for i in self.er_list]
        self.er_ip6_list = [net_conf.tap6_fmt.format(
            0xffff-i) for i in self.er_list]
        if not isinstance(clt_list, (list)):
            clt_list = list(range(GLOBAL_CONF.topo.n_node['clt']))
        self.clt_list = clt_list
        self.clt_ip4_list = [net_conf.clt4_fmt.format(
            i+1) for i in self.clt_list]
        self.clt_ip6_list = [net_conf.clt6_fmt.format(
            i+1) for i in self.clt_list]
        v4_id = 254 - GLOBAL_CONF.topo.n_node['er'] - lb_id
        v6_id = 0xffff - GLOBAL_CONF.topo.n_node['er'] - lb_id
        super().__init__(id=lb_id,
                         node_type='lb',
                         ssh_port=net_conf.lb_mgmt_port+lb_id,
                         mgmt_ip=net_conf.mgmt_fmt.format(v4_id),
                         isvpp=True,
                         hostname='node_lb_{}'.format(lb_id),
                         tap_list=[
                             'lbmgmt{}'.format(lb_id), 
                             'lbvpp{}'.format(lb_id)],
                         l2_list=net_conf.l2_fmt.format(
                             '1b', lb_id),
                         ip4_list=net_conf.tap4_fmt.format(v4_id),
                         ip6_list=net_conf.tap6_fmt.format(v6_id),
                         vcpu_list=GLOBAL_CONF.topo.vcpu_list['lb'][lb_id],
                         physical_server_id=GLOBAL_CONF.topo.physical_server_id['lb'][lb_id],
                        )

    def keys(self):
        return NodeConfig.keys(self) + ('as_list', 'as_ip4_list', 'as_ip6_list',
                                        'gre4_list', 'gre6_list', 'vip4', 'vip6',
                                        'er_list', 'er_ip4_list', 'er_ip6_list',
                                        'clt_list', 'clt_ip4_list', 'clt_ip6_list',
                                        )


class AS_Config(NodeConfig):
    '''configuration for application servers'''

    def __init__(self,
                 as_id,  # id of this as node
                 lb_list=None,  # number of as nodes
                 clt_list=None,  # number of client nodes
                 ):
        net_conf = GLOBAL_CONF.net
        if not isinstance(lb_list, (list)):
            lb_list = list(range(GLOBAL_CONF.topo.n_node['lb']))
        self.lb_list = lb_list
        self.lb_ip4_list = [net_conf.tap4_fmt.format(
            254-GLOBAL_CONF.topo.n_node['er']-i) for i in self.lb_list]
        self.lb_ip6_list = [net_conf.tap6_fmt.format(
            0xffff-GLOBAL_CONF.topo.n_node['er']-i) for i in self.lb_list]
        if not isinstance(clt_list, (list)):
            clt_list = list(range(GLOBAL_CONF.topo.n_node['clt']))
        self.clt_list = clt_list
        self.clt_ip4_list = [net_conf.clt4_fmt.format(
            i+1) for i in self.clt_list]
        self.clt_ip6_list = [net_conf.clt6_fmt.format(
            i+1) for i in self.clt_list]
        self.vip4 = net_conf.as4_vip
        self.vip6 = net_conf.as6_vip
        v4_id = as_id+1
        v6_id = as_id+1
        super().__init__(id=as_id,
                         node_type='as',
                         ssh_port=net_conf.as_mgmt_port+as_id,
                         mgmt_ip=net_conf.mgmt_fmt.format(
                             v4_id),
                         isvpp=False,
                         hostname='node_server_{}'.format(
                             as_id),
                         tap_list=['asmgmt{}'.format(
                             as_id), 'asvpp{}'.format(as_id)],
                         l2_list=net_conf.l2_fmt.format(
                             '52', as_id),
                         ip4_list=net_conf.tap4_fmt.format(
                             v4_id),
                         ip6_list=net_conf.tap6_fmt.format(
                             v6_id),
                         vcpu_list=GLOBAL_CONF.topo.vcpu_list['as'][as_id],
                         physical_server_id=GLOBAL_CONF.topo.physical_server_id['as'][as_id],
                         )

    def keys(self):
        return NodeConfig.keys(self) + ('lb_list', 'lb_ip4_list', 'lb_ip6_list',
                                        'clt_list', 'clt_ip4_list', 'clt_ip6_list',
                                        'vip4', 'vip6')


class ER_Config(NodeConfig):
    '''configuration for edge routers'''

    def __init__(self,
                 er_id,  # id of this lb node
                 lb_list=None,  # number of server nodes
                 ):
        net_conf = GLOBAL_CONF.net
        if not isinstance(lb_list, (list)):
            lb_list = list(range(GLOBAL_CONF.topo.n_node['lb']))
        self.lb_list = lb_list
        self.lb_ip4_list = [net_conf.tap4_fmt.format(
            254-GLOBAL_CONF.topo.n_node['er']-i) for i in self.lb_list]
        self.lb_ip6_list = [net_conf.tap6_fmt.format(
            0xffff-GLOBAL_CONF.topo.n_node['er']-i) for i in self.lb_list]
        self.vip4 = net_conf.as4_vip
        self.vip6 = net_conf.as6_vip
        v4_id = 254 - er_id
        v6_id = 0xffff - er_id
        super().__init__(id=er_id,
                         node_type='er',
                         ssh_port=net_conf.er_mgmt_port+er_id,
                         mgmt_ip=net_conf.mgmt_fmt.format(
                             v4_id),
                         isvpp=True,
                         hostname='node_edge_{}'.format(er_id),
                         tap_list=['ermgmt{}'.format(
                             er_id), 'ervpp{}'.format(er_id)],
                         l2_list=net_conf.l2_fmt.format(
                             'e6', er_id),
                         ip4_list=[net_conf.tap4_fmt.format(
                             v4_id), net_conf.clt4_fmt.format(v4_id)],
                         ip6_list=[net_conf.tap6_fmt.format(
                             v6_id), net_conf.clt6_fmt.format(v6_id)],
                         vcpu_list=GLOBAL_CONF.topo.vcpu_list['er'][er_id],
                         physical_server_id=GLOBAL_CONF.topo.physical_server_id['er'][er_id],
                         )

    def keys(self):
        return NodeConfig.keys(self) + ('lb_list', 'lb_ip4_list', 'lb_ip6_list',
                                        'vip4', 'vip6')


class CLT_Config(NodeConfig):
    global GLOBAL_CONF

    def __init__(self,
                 clt_id,  # id of this lb node
                 er_list=None,  # number of server nodes
                 ):
        net_conf = GLOBAL_CONF.net
        if not isinstance(er_list, (list)):
            er_list = list(range(GLOBAL_CONF.topo.n_node['er']))
        self.er_list = er_list
        self.er_ip4_list = [net_conf.clt4_fmt.format(
            254-i) for i in self.er_list]
        self.er_ip6_list = [net_conf.clt6_fmt.format(
            0xffff-i) for i in self.er_list]
        self.vip4 = net_conf.as4_vip
        self.vip6 = net_conf.as6_vip
        v4_id = clt_id+1
        v6_id = clt_id+1
        super().__init__(id=clt_id,
                         node_type='clt',
                         ssh_port=net_conf.clt_mgmt_port+clt_id,
                         mgmt_ip=net_conf.mgmt_fmt.format(
                             99+v4_id),
                         isvpp=False,
                         hostname='node_client_{}'.format(
                             clt_id),
                         tap_list=['cltmgmt{}'.format(
                             clt_id), 'cltvpp{}'.format(clt_id)],
                         l2_list=net_conf.l2_fmt.format(
                             'ce', clt_id),
                         ip4_list=net_conf.clt4_fmt.format(
                             v4_id),
                         ip6_list=net_conf.clt6_fmt.format(
                             v6_id),
                         vcpu_list=GLOBAL_CONF.topo.vcpu_list['clt'][clt_id],
                         physical_server_id=GLOBAL_CONF.topo.physical_server_id[
                             'clt'][clt_id],
                         )

    def keys(self):
        return NodeConfig.keys(self) + ('er_list', 'er_ip4_list', 'er_ip6_list',
                                        'vip4', 'vip6')

# %%==================================================


if __name__ == '__main__':

    TOPO_CONF = {}
    FILENAME = "unittest-"

    GLOBAL_CONF = GlobalConfig(
        common.COMMON_CONF["dir"]["root"],
        TOPO_CONF,
        common.COMMON_CONF["net"]
    )

    N_SERVER = len(GLOBAL_CONF.net.physical_server_ip)

    # make sure that all vms are within the pool of physical server ips
    for k in NODE_TYPES:
        assert(set(GLOBAL_CONF.to_dict()[
               'topo']['physical_server_id'][k]) - set(range(N_SERVER)) == set())

    # get node config
    NODE_CONF = {i: {k: [] for k in NODE_TYPES} for i in range(N_SERVER)}
    for node_type in NODE_TYPES:
        exec("for i in range(GLOBAL_CONF.topo.n_node['{0}']): \
NODE_CONF[GLOBAL_CONF.topo.physical_server_id['{0}'][i]]['{0}']\
.append(dict({1}_Config(i)))".format(node_type, node_type.upper()))

    # put all config together
    for i in range(N_SERVER):
        if NODE_CONF[i] == {k: [] for k in NODE_TYPES}:
            continue
        config_output = {
            'global': GLOBAL_CONF.to_dict(),
            'nodes': NODE_CONF[i]
        }
        common.json_write2file(config_output, os.path.join(
            GLOBAL_CONF.path.config, 'cluster', FILENAME+'{}.json'.format(i)))
