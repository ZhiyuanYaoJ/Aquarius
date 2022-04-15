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
Check ground truth gathering socket connection
'''
import socket
import sys

# The list of remote hosts
HOST = ['10.0.1.{}'.format(i) for i in range(1, int(sys.argv[1]) + 1)]
PORT = 50008              # The same port as used by the server
def get_err_sockets(host_list, port):
    '''
    @brief: iterate through the host list and get the mal-functioning sockets
    '''
    err = []
    for host in host_list:
        for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
            sock = None
            a_f, socktype, proto, _, s_a = res
            try:
                sock = socket.socket(a_f, socktype, proto)
            except OSError as msg:
                sock = None
                print(msg)
                continue
            try:
                sock.connect(s_a)
            except OSError as msg:
                sock.close()
                sock = None
                print(msg)
                continue
            break
        if sock is None:
            err.append(int(host.split('.')[-1]) - 1)
            # print('{} could not open socket'.format(host))
    return err
print(get_err_sockets(HOST, PORT))
