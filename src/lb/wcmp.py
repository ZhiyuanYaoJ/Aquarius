#!/usr/bin/env python
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
This is the WCMP agent script, run on the LB VMs
'''

#--- Import ---#
import argparse
import numpy as np
import shm_proxy as sm
import env
# import matplotlib.pyplot as plt
# import matplotlib.ticker as ticker


#--- Initialization ---#

def softmax(x):
    '''
    Compute softmax values given sets of scores in x.
    '''
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=0)


class Weighted():
    '''
    @brief: WCMP mechanism
    '''

    def __init__(self, active_as_idx_, weights_, action_dim_, active_=False, logger_=None):
        '''
        @brief:
            This class generate actions (weights) based on features gathered by reservoir sampling
        @param:
            feature_name: the feature name that we use to calculate weights
                          (choose amongst sm.FEATURE_AS_ALL)
            map_func: map function e.g. reciprocal or negative
            alpha: parameter for soft weights update
            logger: logging info
        '''
        self.action_dim = action_dim_
        self.active_as_idx = active_as_idx_
        self.weights = weights_
        self.logger = logger_
        self.init_action = np.zeros(self.action_dim)
        self.init_action[self.active_as_idx] = self.weights[::-1]
        if active_:
            self.get_action = self.get_action_active
        else:
            self.get_action = self.action_repeat

    def action_repeat(self, state_):
        '''
        generate repeatedly action based on the active servers and self.init_action
        '''
        active_as = state_[0]
        assert len(set(active_as) - set(self.active_as_idx)) == 0
        return self.init_action

    def get_action_active(self, state_):
        '''
        generate action for active servers based on the latest state
        '''
        action_ = np.zeros(self.action_dim)
        gt_ = state_[-1]
        active_as = state_[0]
        if len(active_as) > 0:
            load = np.array([gt_[asid][2] for asid in active_as])
            weights = self.init_action[active_as]

            # spotlight implementation (sed-like)
            available_cap = weights/(load+1)
            new_weights = available_cap/max(available_cap)

        else:
            active_as = self.active_as_idx
            new_weights = self.init_action[self.active_as_idx]
        action_[active_as] = new_weights
        return action_

#--- Arguments ---#


PARSER = argparse.ArgumentParser(
    description='Load Balance Environment w/ Openai Gym APIs.')

PARSER.add_argument('-v', action='store_true',
                    default=False,
                    dest='verbose',
                    help='Set verbose mode and print out all info')

PARSER.add_argument('-d', action='store_true',
                    default=False,
                    dest='deploy',
                    help='Set if in deploy mode')

PARSER.add_argument('-i', action='store_true',
                    default=0.25,
                    dest='interval',
                    help='Set sleep interval in env.step() for action to take effect')

PARSER.add_argument('-g', action='store_true',
                    default=False,
                    dest='gt',
                    help='Set if collect ground truth')

PARSER.add_argument('-a', action='store_true',
                    default=False,
                    dest='active',
                    help='Set if active probing is enabled')

PARSER.add_argument('--version', action='version',
                    version='%(prog)s 1.0')

#--- Macros ---#
frame_idx = 0  # number of iterations
MAX_STEPS = 9000  # for dev
RENDER_CYCLE = 2  # every ${RENDER_CYCLE} steps, print out once current state
ACTION_DIM = sm.GLOBAL_CONF['global']['SHM_N_BIN']  # n_as
N_ACTIVE = sm.GLOBAL_CONF['meta']['n_as']
ACTIVE_AS_IDX = list(range(1, 1+N_ACTIVE))
ACTIVE_WEIGHTS = sm.GLOBAL_CONF['meta']['weights']

if __name__ == '__main__':
    LOGGER = env.init_logger("log/lb.log", "rl-logger")

    ARGS = PARSER.parse_args()

    LBENV = env.LoadBalanceEnv(ARGS.interval, LOGGER,
                               verbose=ARGS.verbose, gt=ARGS.gt, deploy=ARGS.deploy)
    state = LBENV.reset()
    ACTOR = Weighted(logger_=LOGGER, active_as_idx_=ACTIVE_AS_IDX,
                     weights_=ACTIVE_WEIGHTS, action_dim_=ACTION_DIM, active_=ARGS.active)

    for step in range(MAX_STEPS):
        action = ACTOR.get_action(state)

        next_state, reward, _, info = LBENV.step(action)

        state = next_state
        last_action = action
        frame_idx += 1

        # render
        if frame_idx % RENDER_CYCLE == 0:
            LBENV.render()
