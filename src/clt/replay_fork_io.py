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
This script replays requests based on a wikipedia log
| The log is assumed to preprocessed (by prettify.sh), such that
| each line corresponds to a request
| Input is read from stdin
---
| example format:
|   1190146243.341 /wiki/Germany
'''
#!/usr/bin/env python3

import resource
import sys
import time
import socket
import struct
import http.client
import os
import threading


def increase_resources():
    '''
    @brief: Increase max number of open files (requires root)
    '''
    resource.setrlimit(resource.RLIMIT_NOFILE, (1048576, 1048576))
    # Drop privileges
    uid, gid = os.getenv('SUDO_UID'), os.getenv('SUDO_GID')
    if uid and gid:
        os.setgid(int(gid))
        os.setuid(int(uid))


# IPv6 addresses corresponding to the VIP
ADDR = '[dead::cafe]'
# Times at which failures happened
failures = []


def run_query(my_url, start_time):
    '''
    @brief: run the query w/ the given url
    '''
    conn = http.client.HTTPConnection(ADDR)
    try:
        conn.connect()
        sock = conn.sock
        # Send RST after FIN, to prevent FIN_WAIT from lingering
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                     struct.pack('ii', 1, 0))
        conn.request('GET', my_url)
        res = conn.getresponse()
    except Exception as e:
        sys.stdout.write("%f %s failed %s\n" % (start_time - t0, my_url, e))
        return
    # Follow one HTTP redirect
    if res.status == 302:
        try:
            conn.request('GET', res.getheader('Location'))
            conn.getresponse()
        except Exception as e:
            sys.stdout.write("%f %s failed %s\n" % (start_time - t0, my_url, e))
            return
    if res.status == 404:
        sys.stdout.write("%f %s failed %s\n" %
                         (start_time - t0, my_url, 'HTTP_404'))
        sock.close()
        return
    res.read()
    sys.stdout.write("%f %s %s\n" %
                     (start_time - t0, my_url, time.time() - start_time))
    sock.close()
    return


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print("Usage: %s <filename>" % sys.argv[0])
        sys.exit(-1)
    filename = sys.argv[1]
    increase_resources()

    # number of seconds elapsed since the beginning of the replay
    ELAPSED_SECONDS = -1

    # list containing (startingTime, url) tuples, corresponding to
    # queries soon to be run
    # invariant: sorted by startingTime
    scheduled = []

    t0 = time.time()

    ## fork n times in order to be able to perform more requests ##
    N_PROCESSES = 8
    IS_CHILD = 0
    for i in range(1, N_PROCESSES):
        if IS_CHILD == 0:
            IS_CHILD = i*int(os.fork() == 0)

    ## open file after fork to have two different copies ##
    file = open(filename, 'r')
    # skip header
    LINE_NO = 1
    file.readline()
    t0log = float(file.readline().split()[0])
    while True:
        t = time.time()

        # When we start a new second, read the corresponding second
        # in the log and schedule appropriate queries
        if t > t0 + ELAPSED_SECONDS + 0.1:
            ELAPSED_SECONDS += 0.1
            while True:
                LINE_NO += 1
                try:
                    line = file.readline()
                except:
                    continue
                if not line:
                    break
                if LINE_NO % N_PROCESSES != IS_CHILD:
                    continue
                try:
                    # retrieve the queries to run between t0+ELAPSED_SECONDS
                    # and t0+ELAPSED_SECONDS+1
                    line = line.split()
                    nextTime = t0 + float(line[0]) - t0log
                    url = line[1]
                except:
                    continue
                scheduled.append((nextTime, url))
                if nextTime > t + 0.1:
                    break
            if not line and not scheduled:
                break

        # Every msec, run scheduled queries
        while scheduled:
            timeToRun, url = scheduled[0]
            if timeToRun < t:
                th = threading.Thread(target=run_query, args=[url, t])
                try:
                    th.start()
                except:
                    sys.stderr.write('Cannot start thread, sleeping for 1s')
                    time.sleep(1)
                scheduled.pop(0)
            else:
                break

        DT = 0.001 - (time.time() - t)
        if DT < 0:
            DT = 0
        time.sleep(DT)  # sleeping for 0 will at least yield

    for th in threading.enumerate():
        if th != threading.currentThread():
            th.join()
