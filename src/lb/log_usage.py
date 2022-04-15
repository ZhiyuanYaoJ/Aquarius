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
log LB resource usage
'''

import time
import psutil

INTERVAL = 0.5
FILENAME = 'log/usage.log'
FILE_ = open(FILENAME, "w")

T0 = time.time()

# print(','.join(['ts', 'cpu_usage', 'used_ram', 'avail_ram']))
FILE_.write(','.join(['ts', 'cpu_usage', 'used_ram', 'avail_ram'])+'\n')
while True:
    time.sleep(INTERVAL)

    CPU_USAGE = psutil.cpu_percent() # gives a single float value
    USED_RAM = psutil.virtual_memory().percent
    AVAIL_RAM = psutil.virtual_memory().available * 100 / psutil.virtual_memory().total

    FILE_.write(','.join([
        str(time.time()-T0),
        '{:.3f}'.format(CPU_USAGE),
        '{:.3f}'.format(USED_RAM),
        '{:.3f}'.format(AVAIL_RAM)
        ])+'\n')

FILE_.close()
