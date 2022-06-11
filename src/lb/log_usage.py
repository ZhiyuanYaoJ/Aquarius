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
import psutil
import time
import argparse
import subprocess
from os import path


def subprocess_cmd(command, debug=False):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    if debug:
        print('@subprocess_cmd: execute {}'.format(command))
    return proc_stdout.decode("utf-8")


interval = 0.5
filename = 'log/usage.log'
f = open(filename, "w")


parser = argparse.ArgumentParser(
    description='Load Balance Log Usage.')

parser.add_argument('-c', action='store_true',
                    default=False,
                    dest='clib',
                    help='Log sys-perf w/ perfmon plugin in VPP and gather cpu-cycles for forwarding in the end')

args = parser.parse_args()

if args.clib:

    time.sleep(5)

    while True:

        # gather sys-perf for 2 rounds
        cmd = 'sudo vppctl set pmc instructions cache-references cache-misses branches branch-misses bus-cycles ref-cpu-cycles page-faults;'
        _ = subprocess_cmd(cmd)
        time.sleep(1)

        if path.exists('done'):
            cmd = 'sudo vppctl sh pmc verbose'
            log_res = subprocess_cmd(cmd)
            f.write('--- perfmon ---\n')
            f.write(log_res+'\n')
            cmd = 'grep -inR "@dt" /var/log/syslog'
            log_res = subprocess_cmd(cmd)
            f.write('--- dt ---\n')
            f.write(log_res+'\n')
            break

    f.close()

else:

    t0 = time.time()

    f.write(','.join(['ts', 'cpu_usage', 'used_ram', 'avail_ram'])+'\n')
    while True:
        time.sleep(interval)

        cpu_usage = psutil.cpu_percent()  # gives a single float value
        used_ram = psutil.virtual_memory().percent
        avail_ram = psutil.virtual_memory().available * 100 / \
            psutil.virtual_memory().total

        f.write(','.join([str(time.time()-t0), '{:.3f}'.format(
            cpu_usage), '{:.3f}'.format(used_ram), '{:.3f}'.format(avail_ram)])+'\n')
        f.flush()

    f.close()
