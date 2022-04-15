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

import subprocess
# import matplotlib.pyplot as plt
# import matplotlib.ticker as ticker


#--- Initialization ---#

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

actual_n_server = 8
threshold = 4
max_n_server = 14

cmd_fmt = 'sudo vppctl lb as dead::cafe/64 dc1b::000{:x}'

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
        if delta > 0 and actual_n_server > 1:
            if actual_n_server <= 8:  # fix the minimum amount of servers allowed
                cmd = 'echo down'
                info = "autoscale: downscale (stay as 10)".format(
                    actual_n_server)
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
    obs_len = 16 # number of steps to store
    obs = np.zeros((max_n_server, obs_len))
    obs_cnt = np.zeros(max_n_server)
    t_init = 10 # slow start time interval
    as_init = range(actual_n_server)

    cmd = 'sudo vppctl lb as dead::cafe/64 dc1b::0009 dc1b::000a dc1b::000b dc1b::000c dc1b::000d dc1b::000e del'
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
        obs[:actual_n_server, step % obs_len] = state[-1][max_n_server -
                                                          actual_n_server + 1:max_n_server+1, 0]
        obs_cnt[:actual_n_server] += 1
        t_now = time.time()
        if t_now - t_last_action < cool_down or t_now - t0 < t_init or step < obs_len:
            continue
        else:
            delta_lo_hi, info = get_cpu_n_lo_hi_delta(obs[obs_cnt > obs_len])
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
