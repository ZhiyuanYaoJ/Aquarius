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
This is the AquaLB agent script, run on the LB VMs
'''
#--- Import ---#
import time
import argparse
import numpy as np
import shm_proxy as sm
import env

#--- Initialization ---#


def softmax(x):
    '''
    Compute softmax values given sets of scores in x.
    '''
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=0)


class AquaLB():
    '''
    @brief: AquaLB mechanism
    '''

    def __init__(
        self,
        feature_name_,
        map_func_,
        action_range_=1.,
        logger_=None,
    ):
        '''
        @brief:
            This class generate actions (weights) based on features gathered by
            reservoir sampling
        @param:
            feature_name_:   the feature name that we use to calculate weights
                            (choose among sm.FEATURE_AS_ALL)
            map_func_:       map function e.g. reciprocal or negative
            action_range_:   by default 1.
            system_mean:    system model's mean value for Kalman Filter
            system_std:     system model's standard deviation for Kalman Filter
            sensor_std:     sensor model's standard deviation for Kalman Filter
            logger_:         logging info
        '''
        self.n_as = sm.GLOBAL_CONF['global']['SHM_N_BIN']  # n_as = num_actions
        self.feature_idx = sm.FEATURE_AS_ALL.index(feature_name_)

        # initialize Kalman-Filter state estimation for each AS node
        self.xs = np.zeros(self.n_as)

        self.map_func = map_func_

        self.logger = logger_
        self.action_range = action_range_

    def calculate_weight(self, feature_as, active_as):
        '''
        @param:
            feature_as: a numpy matrix w/ shape (n_as, n_feature_as)
            active_as: a list of current active application server id
        '''

        new_weights = np.zeros(self.n_as)
        feature = feature_as[active_as, self.feature_idx]

        new_state = feature/(feature.mean()+1e-9)

        # w/ soft update
        # self.xs[active_as] = self.xs[active_as]*0.5+new_state*0.5
        # w/o soft update
        self.xs[active_as] = new_state

        new_weights[active_as] = softmax(self.map_func(self.xs[active_as]))

        return new_weights

    def get_action(self, state_):
        '''
        @return:
            action_: w/ shape [num_actions]
        '''

        active_as, feature_as, _ = state_  # ignore gt

        if len(active_as) == 0:
            return np.ones(self.n_as)

        weights = self.calculate_weight(feature_as, active_as)

        # a mask that leaves only active AS's action
        action_mask = np.zeros_like(weights)
        action_mask[active_as] = self.action_range
        action_ = action_mask * weights

        return action_

    def get_init_action(self, active_as):
        '''
        @brief:
            set weight as 1 for active AS nodes and 0 for the inactive ones
        @return:
            action_: w/ shape [#num_actions]
        '''
        action_ = np.ones(self.n_as)
        # a mask that leaves only active AS's action
        action_mask = np.zeros_like(action_)
        if len(active_as) == 0:
            return action_
        action_mask[active_as] = self.action_range
        return action_mask * action_

#--- Arguments ---#


parser = argparse.ArgumentParser(
    description='Load Balance Environment w/ Openai Gym APIs.')

parser.add_argument('-v', action='store_true',
                    default=False,
                    dest='verbose',
                    help='Set verbose mode and print out all info')

parser.add_argument('-d', action='store_true',
                    default=False,
                    dest='dev',
                    help='Set dev mode and test offline without opening shared memory file')

parser.add_argument('-m', action='store_true',
                    default='alias',
                    dest='method',
                    help='Set method to encode action [\'alias\' for weighted-sampling, \
                         \'score\' for deterministic evaluation]')

parser.add_argument('-i', action='store',
                    default=0.25,
                    dest='interval',
                    help='Set sleep interval in env.step() for action to take effect')

parser.add_argument('-g', action='store_true',
                    default=False,
                    dest='gt',
                    help='Set if collect ground truth')


parser.add_argument('--version', action='version',
                    version='%(prog)s 1.0')

#--- Macros ---#
frame_idx = 0  # number of iterations
MAX_STEPS = 9000  # for dev
RENDER_CYCLE = 2  # every ${RENDER_CYCLE} steps, print out once current state
ACTION_RANGE = 1.
action_dim = sm.GLOBAL_CONF['global']['SHM_N_BIN']  # n_as
FEATURE_NAME = "flow_duration_avg_decay"
def map_func(x):
    '''
    simply calculate the negative of x
    '''
    return -x


# map_func = lambda x: 1/x # option 2: reciprocal
rewards = []

if __name__ == '__main__':
    logger = env.init_logger("log/logger.log", "heuristic-logger")

    args = parser.parse_args()

    lbenv = env.LoadBalanceEnv(args.interval, logger,
                           verbose=args.verbose, gt=args.gt)
    state = lbenv.reset()
    heuristic = AquaLB(FEATURE_NAME, map_func, action_range_=ACTION_RANGE, logger_=logger)
    last_action = heuristic.get_init_action(state[0])

    # initialize
    STEP = 0

    while STEP < MAX_STEPS:
        action = heuristic.get_action(state)

        if (action > 0).any():  # at least one AS has non-zero weight
            next_state, reward, _, info = lbenv.step(action)
        else:
            logger.info(">> no action > 0 ({}), sleep for {:.3f}s".format(
                action, args.interval))
            time.sleep(args.interval)
            continue

        state = next_state
        last_action = action
        frame_idx += 1

        # render
        if frame_idx % RENDER_CYCLE == 0:
            lbenv.render()

        STEP += 1
