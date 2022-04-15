#--- Import ---#
import logging
import sys
import datetime
from os import path

import math
import time
import random
import numpy as np
import gym
from gym import spaces

import shm_proxy as sm
from env import *
import argparse
import struct
import json
from joblib import load

import subprocess
# import matplotlib.pyplot as plt
# import matplotlib.ticker as ticker

from sklearn.pipeline import TransformerMixin
from sklearn.preprocessing import StandardScaler
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import LinearRegression

class Preprocess(TransformerMixin):

    def __init__(self, features, **kwargs):
        """
        Create a transformer to remove outliers. A threshold is set for selection
        criteria, and further arguments are passed to the LocalOutlierFactor class

        Keyword Args:

        Returns:
            object: to be used as a transformer method as part of Pipeline()
        """
        
        self.features = features
        self.idx2log = [i for i,col in enumerate(self.features) if 'byte' in col or 'iat' in col or 'lat' in col]

        self.kwargs = kwargs
        self.scaler = StandardScaler()

    def transform(self, X):
        """
        Uses LocalOutlierFactor class to subselect data based on some threshold

        Returns:
            ndarray: subsampled data

        Notes:
            X should be of shape (n_samples, n_features)
        """
        X = np.asarray(X)
        X[:, self.idx2log] = np.log(X[:, self.idx2log]+1e-6)
        
        return self.scaler.transform(X)

    def fit(self, X, **kwargs):
        X[:, self.idx2log] = np.log(X[:, self.idx2log]+1e-6)
        self.scaler.fit(X)

#--- Initialization ---#

def json_read_file(filename):
    '''
    @brief:
        read data from json file
    '''
    with open(filename, "r") as read_file:
        return json.load(read_file)

def subprocess_cmd(command):
    global VERBOSE
    '''
    pretty print
    '''
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    return proc_stdout.decode("utf-8")

#--- Arguments ---#

parser=argparse.ArgumentParser(
    description = 'Load Balance Environment w/ Openai Gym APIs.')

parser.add_argument('-v', action = 'store_true',
                    default = False,
                    dest = 'verbose',
                    help = 'Set verbose mode and print out all info')

parser.add_argument('-d', action = 'store_true',
                    default = False,
                    dest = 'dev',
                    help = 'Set dev mode and test offline without opening shared memory file')

parser.add_argument('-m', action = 'store_true',
                    default = 'alias',
                    dest = 'method',
                    help = 'Set method to encode action [\'alias\' for weighted-sampling, \'score\' for deterministic evaluation]')

parser.add_argument('-i', action = 'store_true',
                    default = 0.25,
                    dest = 'interval',
                    help = 'Set sleep interval in env.step() for action to take effect')

parser.add_argument('-g', action='store_true',
                    default=False,
                    dest='gt',
                    help='Set if collect ground truth')

parser.add_argument('--version', action = 'version',
                    version = '%(prog)s 1.0')

#--- Macros ---#
frame_idx=0  # number of iterations
max_steps=9000  # for dev
render_cycle=2  # every ${render_cycle} steps, print out once current state
action_range=1.
action_dim=sm.GLOBAL_CONF['global']['SHM_N_BIN']  # n_as
feature_name = "flow_duration_avg_decay"
map_func = lambda x: -x # option 1: negative
# map_func = lambda x: 1/x # option 2: reciprocal
high = 1.
low = 0.5
rewards=[]
action = np.zeros(action_dim) # just take 0 as actions

# auto-scaling
# cpu_threshold_lo = 0.5
# cpu_threshold_hi = 0.8

# actual_n_server = 10
cpu_threshold_lo = 0.7
cpu_threshold_hi = 0.8

actual_n_server = 10
threshold = 4
max_n_server = 14

cmd_fmt = 'sudo vppctl lb as dead::cafe/64 dc1b::000{:x}'


# model related variables
CONF_FILE = "./shm_layout.json"  # layout configuration of shared memory
GLOBAL_CONF = json_read_file(CONF_FILE)
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

FEATURE_NON_SEQ = ['flow_duration_avg',
                    'pt_1st_90',
                    'pt_1st_std',
                    'flow_duration_90',
                    'fct_avg_decay',
                    'flow_duration_std',
                    'pt_1st_avg_decay',
                    'pt_gen_90_decay',
                    'flow_duration_avg_decay',
                    'fct_90_decay',
                    'fct_std',
                    'iat_f_avg_decay',
                    'pt_1st_90_decay',
                    'flow_duration_90_decay',
                    'n_flow_on',
                    'iat_ppf_avg_decay',
                    'iat_ppf_avg',
                    'iat_p_std',
                    'iat_ppf_std',
                    'iat_ppf_90_decay',
                    'iat_f_avg',
                    ]

FEATURE_NON_SEQ_IDX = [i for i, f in enumerate(FEATURE_AS_ALL) if f in FEATURE_NON_SEQ]

preprocessor = load('preprocess.joblib')
lin_reg = load('lin_reg.joblib')

def get_cpu_n_lo_hi_delta(obs):
    '''
    @brief get #as (cpu < cpu_threshold_lo) - #as (cpu > cpu_threshold_hi)
    '''
    global cpu_threshold_hi, cpu_threshold_lo
    cpu_mean = obs.mean(axis=1)
    delta = 0
    for cpu in cpu_mean:
        if cpu < cpu_threshold_lo: delta += 1
        elif cpu > cpu_threshold_hi: delta -= 1
    info = "delta = {}\ncpu_mean = ".format(delta) + ' |'.join(
        [" {:> 5.3f}".format(cpu) for cpu in cpu_mean])
    return delta, info

def make_action(delta, obs_cnt):
    global actual_n_server, max_n_server
    ts, info = None, None
    if abs(delta) > np.ceil(actual_n_server/3):
        if delta > 0:
            if actual_n_server <= 8: # fix the minimum amount of servers allowed
                cmd = 'echo down'
                info = "autoscale: downscale (stay as 10)".format(actual_n_server)
            else:
                cmd = cmd_fmt.format(actual_n_server) + ' del'
                actual_n_server -= 1
                obs_cnt[actual_n_server] = 0
                info = "autoscale: downscale to {}".format(actual_n_server)
        else:
            if actual_n_server >= 14:  # fix the minimum amount of servers allowed
                cmd = 'echo up'
                info = "autoscale: upscale (stay as 14)".format(
                    actual_n_server)
            else:
                actual_n_server += 1
                cmd = cmd_fmt.format(actual_n_server)
                info = "autoscale: upscale to {}".format(actual_n_server)
        ts = time.time()
        subprocess_cmd(cmd)
    return obs_cnt, info, ts

if __name__ == '__main__':

    cool_down = 6 # cool down 2s
    obs_cnt = np.zeros(max_n_server)
    t_init = 10 # slow start time interval
    as_init = range(actual_n_server)

    cmd = 'sudo vppctl lb as dead::cafe/64 dc1b::000b dc1b::000c dc1b::000d dc1b::000e del'
    subprocess_cmd(cmd)

    logger=init_logger("log/lb.log", "rl-logger")

    args=parser.parse_args()

    lbenv = LoadBalanceEnv(args.interval, logger,
                           verbose=args.verbose, gt=args.gt)
    state = lbenv.reset()

    t0 = time.time()
    t_last_action = t0

    for step in range(max_steps):

        state, reward, _, info=lbenv.step(action)
        
        frame_idx += 1

        # auto-scale
        t_now = time.time()
        if t_now - t_last_action < cool_down or t_now - t0 < t_init:
            continue
        else:
            obs = preprocessor.transform(state[-2][max_n_server-actual_n_server+1:max_n_server+1, FEATURE_NON_SEQ_IDX]) # feature_as w/ shape (n_servers, n_features)
            delta_lo_hi, info = get_cpu_n_lo_hi_delta(lin_reg.predict(obs))
            logger.info('[{:6.3f}s] {}\nactual_cpu = '.format(
                t_now - t0, info) + ' |'.join(
                [" {:> 5.3f}".format(cpu) for cpu in state[-1][max_n_server-actual_n_server + 1:max_n_server+1, 0]]))
            obs_cnt, info, t_last_action_new = make_action(
                delta_lo_hi, obs_cnt)
            if info:
                logger.info(info)
                t_last_action = t_last_action_new
        logger.info('autoscale-time: {:.3f}s'.format(time.time()-t_now))

        

        # render
        # if frame_idx % render_cycle == 0:
        #     lbenv.render()
