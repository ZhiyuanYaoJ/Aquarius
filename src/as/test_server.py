#!/usr/bin/env python3
'''
This script is used against connect_server.py to check ping delay between
two docker containers. This file can also run on the server VMs.

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
import _thread

HOST = None               # Symbolic name meaning all available interfaces
PORT = 50008              # Arbitrary non-privileged port

N_THREAD = 2

# init socket
SOCKET = None
for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC,
                              socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
    af, socktype, proto, canonname, sa = res
    try:
        SOCKET = socket.socket(af, socktype, proto)
    except OSError as msg:
        SOCKET = None
        continue
    try:
        SOCKET.bind(sa)
        SOCKET.listen(1)
    except OSError as msg:
        SOCKET.close()
        SOCKET = None
        continue
    break
if SOCKET is None:
    print('could not open socket')
    sys.exit(1)


def listen(conn, addr):
    '''
    @brief: keep listening to request for server state
    '''
    print('Connected by', addr)
    while True:
        # decode message written by other process at [42:110)
        data_recv = conn.recv(42)
        if not data_recv:
            break
        conn.send(('0'*24).encode())  # [cpu:apache:memory:asid]

    conn.close()


# init shared memory
i = 0
while i < 10000:
    CONN, ADDR = SOCKET.accept()
    _thread.start_new_thread(listen, (CONN, ADDR))
    i += 1
SOCKET.close()
