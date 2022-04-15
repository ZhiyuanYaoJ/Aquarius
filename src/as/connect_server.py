#!/usr/bin/env python3
'''
This script is used against test_server.py to check ping delay between
two docker containers.

Copyright (c) 2021 Cisco and/or its affiliates.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at:

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import socket
import sys
import time
import _thread

HOST = '172.17.0.2'               # Symbolic name meaning all available interfaces
PORT = 50008              # Arbitrary non-privileged port

N_THREAD = 2

# init socket
SOCKET = None
for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
    af_, socktype, proto, _, sa_ = res
    try:
        SOCKET = socket.socket(af_, socktype, proto)
    except OSError as msg:
        SOCKET = None
        continue
    try:
        SOCKET.connect(sa_)
    except OSError as msg:
        SOCKET.close()
        SOCKET = None
        print(msg)
        continue
    break
if SOCKET is None:
    print('could not open socket')
    sys.exit(1)


def send():
    '''
    @brief: keep listening to request for server state
    '''
    print("sent 42 for sid!" )
    t0 = time.time() # for overhead comparison
    SOCKET.sendall(b'42\n')  # send query to AS and wait for response
    data = SOCKET.recv(24)  # 24 byte [cpu:memory:apache:as]
    t1 = time.time() # for overhead comparison    
    print("received in {:.9f}s!".format(t1-t0))

# init shared memory
i = 0
while i < 10000:
    send()
    i += 1
    time.sleep(0.05)
SOCKET.close()
