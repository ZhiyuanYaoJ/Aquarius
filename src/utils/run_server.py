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
Boot the VMs on remote servers
'''
import time
import argparse
import testbed_utils as tu

PARSER = argparse.ArgumentParser(description='Run all servers.')

PARSER.add_argument('-f', action='store',
                    default='',
                    dest='config_file',
                    help='configuration file')

PARSER.add_argument('--tr', action='store',
                    default='wiki_600',
                    dest='trace',
                    help='Trace name')

PARSER.add_argument('--sample', action='store',
                    default='hour0.csv',
                    dest='sample',
                    help='Trace sample name')

PARSER.add_argument('-m', action='store',
                    default='aqualb',
                    dest='method',
                    help='LB method')

PARSER.add_argument('--experiment', action='store',
                    default='sc21',
                    dest='experiment',
                    help='Experiment name')

PARSER.add_argument('-n', action='store',
                    default=-1,
                    dest='n_query',
                    help='Number of queries in total')

ARGS = PARSER.parse_args()

tu.init_task_info(
    experiment=ARGS.experiment,
    lb_method=ARGS.method,
    trace=ARGS.trace,
    sample=ARGS.sample,
    cluster_config=ARGS.config_file,
    alias=ARGS.config_file.replace('-0.json', ''),
)

tu.prepare_img(lb_method=ARGS.method, from_orig=None)

# spin up all VMs
tu.runall()

time.sleep(5)

if int(ARGS.n_query) < 0:
    CLIP_N = None
else:
    CLIP_N = int(ARGS.n_query)
tu.prepare_trace_sample(ARGS.trace, ARGS.sample, clip_n=CLIP_N)
