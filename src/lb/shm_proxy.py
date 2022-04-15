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
This script creates a proxy to exchange data with the shared memory
'''
import json
import os
import mmap
import struct
import time
import sys
import argparse
from threading import Thread
import socket
import numpy as np


def json_read_file(filename):
    '''
    @brief:
        read data from json file
    '''
    with open(filename, "r") as read_file:
        return json.load(read_file)

#--- Arguments ---#


CONF_FILE = "./shm_layout.json"  # layout configuration of shared memory
GLOBAL_CONF = json_read_file(CONF_FILE)
N_AS = GLOBAL_CONF['meta']['n_as']
HOST = ['10.0.1.{}'.format(i) for i in range(
    1, N_AS + 1)]   # The list of remote hosts
PORT = 50008              # The same port as used by the server


PARSER = argparse.ArgumentParser(
    description='Shared memory communication interface.')

PARSER.add_argument('--nas', action='store',
                    default=9,
                    dest='n_as',
                    help='Number of AS')

PARSER.add_argument('-g', action='store_true',
                    default=False,
                    dest='gt',
                    help='Set if collect ground truth')

PARSER.add_argument('-v', action='store_true',
                    default=False,
                    dest='verbose',
                    help='Set verbose mode and print out all info')

PARSER.add_argument('-vv', action='store_true',
                    default=False,
                    dest='verbose_debug',
                    help='Set debug mode and print out all debug info')

PARSER.add_argument('-d', action='store_true',
                    default=False,
                    dest='dev',
                    help='Set dev mode and test offline without opening shared memory file')

PARSER.add_argument('--do', action='store_true',
                    default=False,
                    dest='dev_online',
                    help='Set dev online mode and test offline without opening shared memory file')

PARSER.add_argument('-m', action='store',
                    default='',
                    dest='method',
                    help='Method to update msg_in to LB node')

PARSER.add_argument('--list-weight',
                    nargs='+',
                    type=float,
                    default=[1., 1., 2., 2., 1., 1., 2., 2., 2.],
                    dest='weights',
                    help='A list of weights')

PARSER.add_argument('-i', action='store',
                    default=0.5,
                    dest='interval',
                    help='Update interval')

PARSER.add_argument('--version', action='version',
                    version='%(prog)s 1.0')

ARGS = None

#--- Utils ---#


def append_record(filename, record):
    '''
    @brief: append log info to a file
    '''
    with open(os.path.join('log', filename), 'a') as file_target:
        json.dump(record, file_target)
        file_target.write(os.linesep)

def get_sockets(host_list=HOST, port=PORT):
    '''
    @brief: get a list of sockets based on the given host_list
    '''
    sock_all = []
    for host in host_list:
        for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
            sock = None
            af_, socktype, proto, _, sa_ = res
            try:
                sock = socket.socket(af_, socktype, proto)
            except OSError as msg:
                sock = None
                continue
            try:
                sock.connect(sa_)
            except OSError as msg:
                sock.close()
                sock = None
                print(msg)
                continue
            break
        if sock is None:
            print('could not open socket')
            sys.exit(1)
        sock_all.append(sock)
    return sock_all


def gen_alias(weights):
    '''
    @brief:
        generate alias from a list of weights (where every weight should be no less than 0)
    '''
    n_weights = len(weights)
    avg = sum(weights)/(n_weights+1e-6)
    aliases = [(1, 0)]*n_weights
    smalls = ((i, w/(avg+1e-6)) for i, w in enumerate(weights) if w < avg)
    bigs = ((i, w/(avg+1e-6)) for i, w in enumerate(weights) if w >= avg)
    small, big = next(smalls, None), next(bigs, None)
    while big and small:
        aliases[small[0]] = (float(small[1]), int(big[0]))
        big = (big[0], big[1] - (1-small[1]))
        if big[1] < 1:
            small = big
            big = next(bigs, None)
        else:
            small = next(smalls, None)
    return aliases

#--- MACROS ---#


RES_DECAY = 0.9
# counter features gathered for each AS in as_stat_t
FEATURE_AS_CNT = [_[1] for _ in GLOBAL_CONF["vpp"]["struct"]["as_stat"][1:]]
# accumulated feature
FEATURE_AS_CNT_C = [_ for _ in FEATURE_AS_CNT if 'n_flow_on' not in _]
# features gathered for each AS w/ reservoir sampling
FEATURE_AS_RES = [_[1] for _ in GLOBAL_CONF["vpp"]["struct"]["reservoir_as"]]
# features gathered for LB node w/ reservoir sampling
FEATURE_LB_RES = [_[1] for _ in GLOBAL_CONF["vpp"]["struct"]["reservoir_lb"]]
RES_FEATURE_ENG = ["avg", "90", "std", "avg_decay", "90_decay"]
FEATURE_AS_ALL = FEATURE_AS_CNT + \
    ["_".join((a, b)) for a in FEATURE_AS_RES for b in RES_FEATURE_ENG]
# avg AS features and append LB features
FEATURE_LB_ALL = FEATURE_AS_ALL + \
    ["_".join((a, b)) for a in FEATURE_LB_RES for b in RES_FEATURE_ENG]
GT = ["cpu", "memory", "apache", "asid"]

# get the mapping between ASID in VPP LB node and actual host id
AS_MAP_VPP2HOSTID = {N_AS - i: i for i in range(N_AS)}  # v6
AS_MAP_HOSTID2VPP = {v: k for k, v in AS_MAP_VPP2HOSTID.items()}

#--- Class ---#


class ShmManager():
    '''
    a class that manage and interacte the shared memory file
    '''

    #--- private utils ---#

    def __init_shm(self, filename):
        '''
        @brief:
            initialize shared memory and get ptr to the whole chunk
        @params:
            filename: shared memory file name
            size: size of the shared memory
            offset: starting point of the actually used shared memory
        @return:
            (array) ptr -> actually used shared memory
        '''
        file_target = open(filename, "r+")
        # whole shared memory
        self._mem = mmap.mmap(file_target.fileno(), self.shm_size,
                              mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, 0)

    def __get_n_element(self, var):
        '''
        @brief
            parse number of element for a variable in a struct, distinguish
            whether it's a single element or an array
        @params:
            var: (type, variable, #(array if > 1), description, default value)
            conf: global configuration concerning variable definitions
        @return:
            (int) number of elements
        '''
        res = var[2]
        if isinstance(res, str):
            res = self.global_conf[res]
        assert isinstance(res, int)
        return res

    def __pytypeof(self, var_list):
        '''
        @brief:
            convert list of variables in c into corresponding string of
            data type in python
        @params:
            var_list: list of variables
                      [
                          (type, variable, #(array if > 1), description, default value),
                          ...
                      ]
        @return:
            (str) packed data type
        '''
        # convert single variable into list if necessary
        if not isinstance(var_list[0], list):
            var_list = [var_list]
        res = ""
        for var_ in var_list:
            if var_[0] in self.maps["ctype2pytype"].keys():
                res += self.maps["ctype2pytype"][var_[0]] * \
                    self.__get_n_element(var_)
            elif var_[0] in self.structs.keys():
                res += self.__pytypeof(self.structs[var_[0]]) * \
                    self.__get_n_element(var_)
            else:
                print("Error processing: {}".format(var_))
                return None
        return res

    def __pytypeof_type(self, var_type):
        '''
        @brief:
            convert a specific data type in c into corresponding string of data type in python
        @params:
            var_type: (str) (type, variable, #(array if > 1), description, default value)[0]
        @return:
            (str) packed data type
        '''
        assert isinstance(var_type, str)
        if var_type in self.maps["ctype2pytype"].keys():
            res = self.maps["ctype2pytype"][var_type]
        elif var_type in self.structs.keys():
            res = self.__pytypeof(self.structs[var_type])
        else:
            print("@__pytypeof_type: Error processing: {}".format(var_type))
            res = None
        return res

    def __sizeof(self, var_list):
        '''
        @brief:
            get the size of list of variables in c
        @params:
            var_list: list of variables
                      [
                          (type, variable, #(array if > 1), description, default value),
                          ...
                      ]
        @return:
            (str) packed data type
        '''
        # convert single variable into list if necessary
        if not isinstance(var_list[0], list):
            var_list = [var_list]
        res = 0
        for var_ in var_list:
            if var_[0] in self.maps["ctype2byte"].keys():
                res += self.maps["ctype2byte"][var_[0]] * self.__get_n_element(var_)
            elif var_[0] in self.structs.keys():
                res += self.__sizeof(self.structs[var_[0]]) * \
                    self.__get_n_element(var_)
            else:
                print("Error processing: {}".format(var_))
                return None
        return res

    def __sizeof_type(self, var_type):
        '''
        @brief:
            get the size of a given data type
        @params:
            var_type: (str) (type, variable, #(array if > 1), description, default value)[0]
        @return:
            (str) packed data type
        '''
        assert isinstance(var_type, str)
        if var_type in self.maps["ctype2byte"].keys():
            res = self.maps["ctype2byte"][var_type]
        elif var_type in self.structs.keys():
            res = self.__sizeof(self.structs[var_type])
        else:
            print("Error processing: {}".format(var_type))
            res = None
        return res

    def __init_ptrs(self, mem, var_list):
        '''
        @brief:
            Initialize ptrs to all the fields
        @params:
            mem: chunk of memory
            var_list: list of variables
                      [
                          (type, variable, #(array if > 1), description, default value),
                          ...
                      ]
        @return:
            e.g.: ptrs = {
                    "n_as": [
                        {
                            "type": "B"
                            "mem": [0]
                            "child": {}
                        },
                    ]
                    "ref": [
                        {
                            "type": "IIff"
                            "mem": [1, 2, ... 16],
                            "child": {
                                "t0_lb": {
                                    "I"
                                    "mem": [1, 2, 3, 4]
                                    "child": {}
                                },
                                ...
                            }
                        },
                        ...
                    ],
                    ...
                }
        '''

        res = {}
        offset = 0
        for var_ in var_list:
            data_type = var_[0]
            key = var_[1]
            # (unit) size of this data type
            _sz = self.__sizeof_type(data_type)
            # (unit) pytype of this data type
            _type = self.__pytypeof_type(data_type)
            n_element = self.__get_n_element(var_)  # number of elements (>1 if array)
            res[key] = []
            while n_element > 0:
                n_element -= 1
                _mem = mem[offset:(offset+_sz)]
                if data_type in self.maps["ctype2byte"].keys():
                    _child = {}
                elif data_type in self.structs.keys():
                    _child = self.__init_ptrs(_mem, self.structs[data_type])
                else:
                    print("@__init_ptrs: Error process ", var_)
                    return None
                tmp = {
                    "type": _type,
                    "mem": [_mem[0], _mem[-1]+1],
                    "child": _child,
                }
                res[key].append(tmp)
                offset += _sz
        return res

    def __write2shm(self, ptr, content):
        '''
        @brief: write content in bytes to shared memory w/ ptr info
        @params:
            ptr: a class that contains e.g.:
                        {
                            "type": "B"
                            "mem": [0]
                            "child": {
                                ...
                            }
                        }
            content: in bytes
        '''
        self._mem[ptr["mem"][0]:ptr["mem"][1]] = content

    #--- initialization ---#

    def __init__(self, conf_file, verbose=False, verbose_debug=False, gt=False, deploy=True):
        '''
        @brief:
            initialization, get configuration, initialize shared memory, etc.
        @params:
            conf_file: configuration file w/ json format
        '''
        # get configuration from json file
        self.shm_conf = json_read_file(conf_file)
        self.global_conf = self.shm_conf["global"]
        self.maps = self.shm_conf["map"]
        self.structs = self.shm_conf["vpp"]["struct"]
        self.layout = self.shm_conf["layout"]
        # initialize incremental counters
        self.id_out = 0
        self.id_in = 0
        # init frame mask
        # e.g. 0x3 if SHM_N_FRAME = 4
        self.frame_mask = self.global_conf["SHM_FRAME_MASK"]
        # initialize sructs info wrt. self.structs
        self.struct_pytypes = {k: self.__pytypeof(
            v) for k, v in self.structs.items()}
        self.struct_sizes = {k: self.__sizeof(
            v) for k, v in self.structs.items()}
        # initialize ptrs wrt. self.layout
        self.shm_size = self.global_conf["SHM_SIZE"]
        self.shm_offset = self.global_conf["SHM_OFFSET"]
        self.ptrs = self.__init_ptrs(
            list(range(self.shm_offset, self.shm_size)), self.layout)
        self.shm_n_bin = self.global_conf["SHM_N_BIN"]
        self.res_n_bin = self.global_conf["RESERVOIR_N_BIN"]
        self.n_as = N_AS
        self.as_map_hostid2vpp = AS_MAP_HOSTID2VPP
        # initialize as_stat buffer
        self.stat_last = {}
        for asid in range(self.shm_n_bin):
            self.stat_last[asid] = {v[1]: 0 if 'u' in v[0]
                                          else 0. for v in self.structs["as_stat"]}
            self.stat_last[asid]['ts'] = 0  # init timestamp
        if ARGS is None or not ARGS.dev:
            # initialize shared memory
            self.__init_shm(filename=self.global_conf["FILE_FMT"].format(
                self.global_conf["VIP_ID"]))
        # initialize active ASs
        self.active_ass = []
        self.ground_truth = gt
        self.gt_sockets = []
        if gt:  # gather all features
            self.gt_sockets = get_sockets(HOST, PORT)
        if deploy: # enable deploy mode and ignore feature lb
            self.process_reservoir = self.__process_reservoir_deploy
            self.parse_frame_out = self.__parse_frame_out_deploy
        else:
            self.process_reservoir = self.__process_reservoir_non_deploy
            self.parse_frame_out = self.__parse_frame_out_non_deploy
        self.verbose = verbose
        self.verbose_debug = verbose_debug

    #--- public methods ---#

    def unpack_mem(self, ptr):
        '''
        @brief:
            unpack shared memory into python struct based on the defined type string
        '''
        return struct.unpack(ptr["type"], self._mem[ptr["mem"][0]:ptr["mem"][1]])

    def get_shm_info(self):
        '''
        @brief:
            print out shared memory layout information
        '''
        print("--- Shm info ---")
        for conf in self.global_conf.keys():
            print("{}: {}".format(conf, self.global_conf[conf]))
        for layout_ in self.layout:
            key = layout_[1]
            print(">> {}".format(key))
            for frame in self.ptrs[key]:
                print(frame['mem'])
        print("----------------")

    def get_frame_sid_out(self, fid):
        '''
        @brief:
            get sequence id given msg_out_frame index
        @params:
            fid: frame index
        @return:
            (u32)
        '''
        assert 0 <= fid < self.global_conf["SHM_N_FRAME"]
        ptr = self.ptrs["msg_out_frames"][fid]["child"]["id"][0]
        return self.unpack_mem(ptr)[0]

    def get_field_from_frame(self, frame, field, _id=0):
        '''
        @brief:
            read and parse fields from given frame
        @params:
            frame: (dict) ptr to the frame
            field: (str) field name in {"id", "ts", "b_header", "body"}
            _id: (int) index of the array (default is 0, need to specify when field is "body")
        @return:
            if field's data type is a single variable -> return 1 value
            if field's data type is a list of variables -> return a dictionary
        '''
        assert(field in [f[1] for f in self.structs['msg_out']]
               )  # make sure that we are querying a field from msg_out
        ptr = frame["child"][field][_id]
        res = self.unpack_mem(ptr)
        if len(ptr["type"]) > 1:
            res = {self.structs["as_stat"][i][1]: v for i, v in enumerate(res)}
        else:
            res = res[0]
        return res

    def get_active_as(self, frame):
        '''
        @brief:
            get the list of active AS from message frames
        @params:
            frame: ptr to the frame
        '''
        b_header = self.get_field_from_frame(frame, "b_header")
        bits = ("{:0"+str(self.shm_n_bin)+"b}").format(b_header)
        return [i for i, v in enumerate(bits) if v == '1']

    def get_active_as_all(self, frame):
        '''
        @brief:
            get the list of active AS from message frames as
        @params:
            frame: ptr to the frame
        '''
        b_header = self.get_field_from_frame(frame, "b_header")
        return [int(i) for i in ("{:0"+str(self.shm_n_bin)+"b}").format(b_header)]

    def process_as_stat(self, frame, asid, ts_):
        '''
        @brief:
            process basic statistics from the observations
        @return:
            a list of features in FEATURE_AS_CNT
        '''
        as_stat = self.get_field_from_frame(frame, "body", asid)
        stat_last = self.stat_last[asid]
        assert ts_ >= stat_last["ts"]
        as_stat["ts"] = ts_  # add timestamp
        res = np.zeros(len(FEATURE_AS_CNT))  # initialize result dictionary
        for i, feature in enumerate(FEATURE_AS_CNT):
            if feature in FEATURE_AS_CNT_C:
                res[i] = as_stat[feature] - stat_last[feature]
            else:
                res[i] = as_stat[feature]
        self.stat_last[asid] = as_stat
        return res

    def __process_reservoir_deploy(self, asid, ts_):
        '''
        @brief:
            process reservoir samples from the observations
        @params:
            asid: 0 <= asid < SHM_N_BIN
        @return:
            a list of features in FEATURE_AS
        '''
        reservoir = self.unpack_mem(self.ptrs["res_as"][asid])
        res = np.zeros(len(FEATURE_AS_RES) * len(RES_FEATURE_ENG))
        for i, _ in enumerate(FEATURE_AS_RES):
            t_samples = np.array([reservoir[i*2*self.res_n_bin + 2*j]
                                  for j in range(self.res_n_bin)])
            v_samples = np.array([reservoir[i*2*self.res_n_bin + 2*j + 1]
                                  for j in range(self.res_n_bin)])
            base_ = i*5
            res[base_] = np.mean(v_samples)  # avg
            res[base_+1] = np.percentile(v_samples, 90)  # 90 percentile
            res[base_+2] = np.std(v_samples)  # stddev
            # calculate value that decay with time
            v_decay = np.multiply(
                v_samples, np.power(RES_DECAY, ts_-t_samples))
            res[base_+3] = np.mean(v_decay)  # avg decay
            res[base_+4] = np.percentile(v_decay, 90)  # 90 percentile decay
        return res

    def __process_reservoir_non_deploy(self, asid, ts_):
        '''
        @brief:
            process reservoir samples from the observations
        @params:
            asid: if asid == -1, get "res_lb", if 0 <= asid < SHM_N_BIN
        @return:
            a list of features in FEATURE_AS
        '''
        if asid < 0:
            reservoir = self.unpack_mem(self.ptrs["res_lb"][0])
            feature_list = FEATURE_LB_RES
        else:
            reservoir = self.unpack_mem(self.ptrs["res_as"][asid])
            feature_list = FEATURE_AS_RES
        res = np.zeros(len(feature_list) * len(RES_FEATURE_ENG))
        for i in range(len(feature_list)):
            t_samples = np.array([reservoir[i*2*self.res_n_bin + 2*j]
                                  for j in range(self.res_n_bin)])
            v_samples = np.array([reservoir[i*2*self.res_n_bin + 2*j + 1]
                                  for j in range(self.res_n_bin)])
            base_ = i*5
            res[base_] = np.mean(v_samples)  # avg
            res[base_+1] = np.percentile(v_samples, 90)  # 90 percentile
            res[base_+2] = np.std(v_samples) # stddev
            # calculate value that decay with time
            v_decay = np.multiply(v_samples, np.power(RES_DECAY, ts_-t_samples))
            res[base_+3] = np.mean(v_decay)  # avg decay
            res[base_+4] = np.percentile(v_decay, 90)  # 90 percentile decay
        return res

    def process_as_feature(self, sid, frame, asid, ts_, res, gt_=None):
        '''
        @brief:
            (only called by main)
            process observations and output:
            +- if gt:
            |    return (observation, gt) as a tuple
            +- else:
            |    return observation
        @params:
            sid: sequence id of the frame
            frame: ptr to a msg_out_frame
            asid: id of the AS to be processed
            ts_: timestamp
        '''
        if self.ground_truth:  # collect ground truth data
            sock = self.gt_sockets[AS_MAP_VPP2HOSTID[asid]]
            sock.sendall(b'42\n')  # send query to AS and wait for response
            if self.verbose_debug:
                print("sent 42 for sid {:d}!".format(sid))

        # update stats from observations
        res_stat = self.process_as_stat(frame, asid, ts_)
        # update reservoir sampling observations
        res_reservoir = self.process_reservoir(asid, ts_)
        # merge the two dicts
        res[asid] = np.concatenate((res_stat, res_reservoir))
        
        if self.ground_truth:  # collect ground truth data
            if self.verbose_debug:
                print("waiting for reply...")
            data = sock.recv(24)  # 24 byte [cpu:memory:apache:as]
            if self.verbose_debug:
                print("reply received!")
            gt_[asid] = np.array(struct.unpack('dqii', data))

    def __parse_frame_out_deploy(self, sid, frame):
        '''
        Create a bunch of threads each of which deals with one AS
        @note:  modify target function to parse in different ways
        '''
        self.active_ass = self.get_active_as(frame)
        ts_ = self.get_field_from_frame(frame, "ts")
        feature_as = np.zeros((self.shm_n_bin, len(FEATURE_AS_ALL)))
        ground_truth = None
        if self.ground_truth:
            ground_truth = np.zeros((self.shm_n_bin, len(GT)))

        threads = [Thread(target=self.process_as_feature, args=(
            sid, frame, asid, ts_, feature_as, ground_truth)) for asid in self.active_ass]
        for th_ in threads:
            th_.start()
        for th_ in threads:
            th_.join()
        

        return (self.active_ass, None, feature_as, ground_truth)

    def __parse_frame_out_non_deploy(self, sid, frame):
        '''
        Create a bunch of threads each of which deals with one AS
        @note:  modify target function to parse in different ways
        '''
        self.active_ass = self.get_active_as(frame)
        ts_ = self.get_field_from_frame(frame, "ts")
        feature_as = np.zeros((self.shm_n_bin, len(FEATURE_AS_ALL)))
        ground_truth = None
        if self.ground_truth:
            ground_truth = np.zeros((self.shm_n_bin, len(GT)))
        threads = [Thread(target=self.process_as_feature, args=(
            sid, frame, asid, ts_, feature_as, ground_truth)) for asid in self.active_ass]
        for th_ in threads:
            th_.start()
        feature_lb_res = self.process_reservoir(-1, ts_)
        for th_ in threads:
            th_.join()
        if len(self.active_ass) > 0:
            if self.verbose_debug:
                print(
                    "@shm_proxy | parse_frame_out: active_as w/ length {}".format(
                        len(self.active_ass)
                    ))
            feature_as_avg = feature_as[self.active_ass, :].mean(axis=0)
        else:
            if self.verbose_debug:
                print("@shm_proxy | parse_frame_out: active_as w/ length 0")
            feature_as_avg = np.zeros(len(FEATURE_AS_ALL))
        feature_lb = np.concatenate((feature_as_avg, feature_lb_res))

        return (self.active_ass, feature_lb, feature_as, ground_truth)

    def register_as_alias(self, seq_id, alias):
        '''
        @brief:
            save alias tuple into shared memory `msg_in_frames`
        @params:
            seq_id: sequential number of the msg_in, determining in which frame msg is stored
        '''
        ptr = self.ptrs["msg_in_frames"][seq_id & self.frame_mask]
        alias = struct.pack(ptr["type"], 0, time.time(
        ), *[0.]*self.shm_n_bin, *[item for lt in alias for item in lt])
        self.__write2shm(ptr, alias)
        # put the lock by updating seq_id
        alias_id = struct.pack("I", seq_id)
        ptr_id = ptr["child"]["id"][0]
        self.__write2shm(ptr_id, alias_id)

    def register_as_weights(self, seq_id, weights):
        '''
        @brief:
            save alias tuple into shared memory `msg_in_frames`
        @params:
            seq_id: sequential number of the msg_in, determining in which frame msg is stored
            weights: a list w/ length=SHM_N_BIN where 0 means AS is not active
        '''
        # generate alias w/ weights
        alias = [(1., 0)] * self.shm_n_bin
        non_zero_weights = [v for v in weights if v > 0]
        non_zero_weights_id = [i for i, v in enumerate(weights) if v > 0]

        non_zero_alias = gen_alias(non_zero_weights)

        for alias_, asid in zip(non_zero_alias, non_zero_weights_id):
            alias[asid] = (alias_[0], alias_[1])

        ptr = self.ptrs["msg_in_frames"][seq_id & self.frame_mask]
        packed_info = struct.pack(ptr["type"], 0, time.time(
        ), *weights, *[item for lt in alias for item in lt])
        self.__write2shm(ptr, packed_info)
        # put the lock by updating seq_id
        sid = struct.pack("I", seq_id)
        ptr_id = ptr["child"]["id"][0]
        self.__write2shm(ptr_id, sid)

    def get_latest_sid_out(self):
        '''
        @brief:
            obtain the largest sequence id in the observation frames by traversing all the frames
        '''
        sid = self.get_frame_sid_out((self.id_out + 1) & self.frame_mask)
        while self.id_out < sid:
            self.id_out = sid
            sid = self.get_frame_sid_out((self.id_out + 1) & self.frame_mask)
        return self.id_out

    def get_current_active_as(self):
        '''
        @brief:
            obtain the latest info about active AS from binary header
        '''
        sid = self.get_latest_sid_out()
        frame = self.ptrs["msg_out_frames"][sid & self.frame_mask]
        return self.get_active_as(frame), sid

    def get_latest_frame(self):
        '''
        @brief:
            return observation with the latest buffer frame and reservoir samples
        @return:
            a tuple consists of (active_as, feature_lb, feature_as, gt)
        '''
        sid = self.get_frame_sid_out((self.id_out + 1) & self.frame_mask)
        while self.id_out < sid:  # keep traversing until we hit the latest entry in the frames
            self.id_out = sid
            sid = self.get_frame_sid_out((self.id_out + 1) & self.frame_mask)
        frame = self.ptrs["msg_out_frames"][self.id_out & self.frame_mask]
        res = self.parse_frame_out(self.id_out, frame)
        if self.verbose:
            result = {'ts': time.time()}
            result.update({k: v.tolist() for k, v in zip(
                ["active_as", "feature_lb", "feature_as", "gt"], res
            ) if isinstance(v, np.ndarray)})
            result.update({k: v for k, v in zip(
                ["active_as", "feature_lb", "feature_as", "gt"], res
            ) if not isinstance(v, np.ndarray)})
            append_record("shm.json", result)
        return res

    def run(self):
        '''
        @brief:
            run the ShmManager (only called by main)
        '''

        while True:
            _t0 = time.time()
            # 4-frame (5-buffering)
            sid = self.get_frame_sid_out((self.id_out + 1) & self.frame_mask)
            while self.id_out < sid:  # keep traversing until we hit the latest entry in the frames
                self.id_out = sid
                if self.verbose_debug:
                    print(">> New sid! ", sid)
                frame = self.ptrs["msg_out_frames"][sid & self.frame_mask]
                result = {'ts': time.time()}
                result_frame = self.parse_frame_out(sid, frame)
                result.update({k: v.tolist() for k, v in zip(
                    [
                        "active_as", "feature_lb", "feature_as", "gt"
                    ],
                    result_frame
                    ) if isinstance(v, np.ndarray)})
                result.update({k: v for k, v in zip(
                    [
                        "active_as", "feature_lb", "feature_as", "gt"
                    ],
                    result_frame
                    ) if not isinstance(v, np.ndarray)})
                if self.verbose:
                    append_record("shm.json", result)
                sid = self.get_frame_sid_out(
                    (self.id_out + 1) & self.frame_mask)
            dt_ = time.time() - _t0
            if self.verbose_debug:
                print("[{:.4f}] main thread: spent time {:.4f}s".format(
                    time.time(), dt_))
            # sleep a bit to gather observation until next collection
            time.sleep(max(self.global_conf["SHM_UPT_DT"] - dt_, 0.))

    def dev(self):
        '''
        @brief: off-line dev function
        '''
        print("Yo! This is dev mode!")
        self.get_shm_info()
        print("FEATURE_AS: ", FEATURE_AS_ALL)
        print("FEATURE_LB: ", FEATURE_LB_ALL)
        print("GT: ", GT)

    def dev_online(self):
        '''
        @brief:
            process reservoir samples from the observations
        '''
        print(self.ptrs.keys())
        n_as = self.unpack_mem(self.ptrs["n_as"][0])[0]
        print("n_as = {}".format(n_as))
        data = self.unpack_mem(self.ptrs["msg_out_cache"][0])
        print(">> id {} | ts {} | b_header {:x} ".format(
            data[0], data[1], data[2]))

        target_as = [0, 1]
        for as_id in target_as:
            res = self.unpack_mem(self.ptrs["res_as"][as_id])
            print("=== as{} ===".format(as_id))
            print("ts: ", str(res[::2]))
            print("value: ", str(res[1::2]))


#-- main --#
if __name__ == '__main__':
    ARGS = PARSER.parse_args()

    SHM_M = ShmManager(CONF_FILE, verbose=ARGS.verbose,
                       verbose_debug=ARGS.verbose_debug, gt=ARGS.gt)
    if ARGS.dev_online:
        SHM_M.dev_online()
    elif not ARGS.dev:
        SHM_M.run()
    else:
        SHM_M.dev()
