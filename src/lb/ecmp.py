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
This is the ECMP agent script, run on the LB VMs
'''
#--- Import ---#
import argparse
import numpy as np
import shm_proxy as sm
import env


#--- Arguments ---#


parser = argparse.ArgumentParser(
    description='Load Balance Environment w/ Openai Gym APIs.')

parser.add_argument('-v', action='store_true',
                    default=False,
                    dest='verbose',
                    help='Set verbose mode and print out all info')

parser.add_argument('-i', action='store_true',
                    default=0.25,
                    dest='interval',
                    help='Set sleep interval in env.step() for action to take effect')

parser.add_argument('-g', action='store_true',
                    default=False,
                    dest='gt',
                    help='Set if collect ground truth')

parser.add_argument('-d', action='store_true',
                    default=False,
                    dest='deploy',
                    help='Set if in deploy mode')

parser.add_argument('--version', action='version',
                    version='%(prog)s 1.0')

#--- Macros ---#
frame_idx = 0  # number of iterations
MAX_STEPS = 9000  # for dev
RENDER_CYCLE = 2  # every ${RENDER_CYCLE} steps, print out once current state
ACTION_RANGE = [0.5, 1]
ACTION_DIM = sm.GLOBAL_CONF['global']['SHM_N_BIN']  # n_as

rewards = []
action = np.zeros(ACTION_DIM)  # just take 0 as actions

if __name__ == '__main__':
    logger = env.init_logger("log/lb.log", "rl-logger")

    args = parser.parse_args()

    lbenv = env.LoadBalanceEnv(args.interval, logger,
                           verbose=args.verbose, gt=args.gt, deploy=args.deploy)
    state = lbenv.reset()

    for step in range(MAX_STEPS):

        next_state, reward, _, info = lbenv.step(action)

        state = next_state
        frame_idx += 1

        # render
        if frame_idx % RENDER_CYCLE == 0:
            lbenv.render()
