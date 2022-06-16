#!/usr/bin/env python
# coding: utf-8
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
This script defines utility functions that help run the testbed experiments
'''

# %%==================================================
# import dependencies
import os
import time
import subprocess
import warnings
# gives us access to global configurations, e.g. what is used as VLAN interface
import common

# %%==================================================
# macro & global variables
CONFIG = {}  # configuration of testbed
NODES = {}  # a dictionary of all node instances of different type
LOOP_DIR = '/mnt/loop'
VERBOSE = False
LB_METHOD = 'maglev'
LB_METHOD_LAST_BUILD = 'maglev'
DIRNAME = os.path.dirname(__file__)

# %%==================================================
# lower-level utils

class FileNotExistWarning(UserWarning):
    '''
    A placeholder for one type of warning
    '''
    pass


def subprocess_cmd(command):
    '''
    execute command and print out result
    '''
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    return proc_stdout.decode("utf-8")


# %%==================================================
# system operation functions

def mount_new_image(img_orig, img_new):
    '''
    mount new image: img_orig -> img_new
    @param:
        img_orig: original image
        img_new: target
    '''
    if VERBOSE:
        print(">> Mounting image: {}...".format(img_new), end='\r')
    cmd = "rm -f {0};\
    qemu-img create -f qcow2 -b {1} {0};\
    sudo modprobe nbd max_part=8;\
    sudo qemu-nbd --connect=/dev/nbd0 {0};\
    sudo mount -o loop /dev/nbd0p1 {2};\n".format(img_new, img_orig, LOOP_DIR)
    subprocess_cmd(cmd)
    if VERBOSE:
        print(">> Mounting image {} done!".format(img_new))


def mount_image(img):
    '''
    mount image: img
    @param:
        img: image to be mounted
    @e.g.:
        mount_image(CONFIG['img']['base'])
        # then run `sudo chroot /mnt/loop/ /bin/bash` to check something like:
        # `apt list --installed | grep vpp`
    '''
    if VERBOSE:
        print(">> Mounting image: {}...".format(img), end='\r')
    cmd = "sudo modprobe nbd max_part=8;\
    sudo qemu-nbd --connect=/dev/nbd0 {};\
    sudo mount -o loop /dev/nbd0p1 {};\
    \n".format(img, LOOP_DIR)
    subprocess_cmd(cmd)
    if VERBOSE:
        print(">> Mounting image done!")


def copy_files(src, dst, isfolder=False, sudoer=True):
    '''
    copy files from src to dst
    @param:
        src/dst: path on the machine
    '''
    if VERBOSE:
        print("- Copy from {} to {}...".format(src, dst), end='\r')
    r_placeholder = ' '
    if isfolder:
        r_placeholder = ' -r '
    if sudoer:
        cmd = "sudo cp{}{} {}".format(r_placeholder, src, dst)
    else:
        cmd = "cp{}{} {}".format(r_placeholder, src, dst)
    subprocess_cmd(cmd)
    if VERBOSE:
        print("- Copy from {} to {} done!".format(src, dst))


def umount_image():
    '''
    cleanup mounted image (umount and disconnect)
    '''
    if os.path.exists('{}/home/cisco'.format(LOOP_DIR)):
        if VERBOSE:
            print(">> Umounting image...")
        cmd = "sudo chown 1000:1000 {0}/home/cisco/*;\
        sudo umount {0}/;\
        sudo qemu-nbd --disconnect /dev/nbd0;\n".format(LOOP_DIR)
        subprocess_cmd(cmd)
        if VERBOSE:
            print(">> Umounting image done!")


def write2file_tee(content, filename, attach_mode=False, debug_mode=None):
    '''
    write content to filename
    @param:
        content: string
        filename: in form of os.path
        attach_mode: by default turn off
                    change to '-a' s.t. content will be attached to the end of the file
        debug_mode: by default turn off
                    change to whatever s.t. content will be printed out
    '''
    if attach_mode:
        attach = '-a '
    else:
        attach = ''
    if debug_mode:
        cmd = 'sudo echo \"{}" | sudo tee {}{}'.format(content, attach, filename)
    else:
        cmd = 'sudo echo \"{}" | sudo tee {}{} > /dev/null'.format(
            content, attach, filename)
    subprocess_cmd(cmd)


def tap_down(tap_list):
    '''
    take down all tap interfaces
    @param:
        tap_list: list of tap interface names
    '''
    cmd = ""
    for tap in tap_list:
        cmd += "sudo tunctl -d {};".format(tap)
    subprocess_cmd(cmd)


def tap_up(tap_list):
    '''
    bring up all tap interfaces
    @param:
        tap_list: list of tap interface names
    '''
    cmd = ""
    for tap in tap_list:
        cmd += "sudo tunctl -t {0}; sudo ifconfig {0} mtu 1500 up;".format(tap)
    subprocess_cmd(cmd)


def br_up():
    '''
    setup bridge if needed
    '''

    bridge = CONFIG['global']['net']['bridge']
    mgmt_bridge = CONFIG['global']['net']['mgmt_bridge']
    # if the bridge does not exists
    if ~os.path.isfile(os.path.join("/sys/devices/virtual/net", bridge)):
        cmd = "sudo brctl addbr {0};\
        sudo brctl setageing {0} 9999999;\
        sudo ifconfig {0} up;\
        sudo brctl addbr {1};\
        sudo brctl setageing {1} 9999999;\
        sudo ifconfig {1} up;".format(
            bridge,
            mgmt_bridge)
        subprocess_cmd(cmd)


def br_down():
    '''
    tear down bridge
    '''
    bridge = CONFIG['global']['net']['bridge']
    mgmt_bridge = CONFIG['global']['net']['mgmt_bridge']
    cmd = "sudo brctl delif {0};\
    sudo ifconfig {0} down;\
    sudo brctl delbr {0};\
    sudo brctl delif {1};\
    sudo ifconfig {1} down;\
    sudo brctl delbr {1};".format(
        bridge,
        mgmt_bridge)
    subprocess_cmd(cmd)


def pin_qemu(port, *argv):
    '''
    pin qemu thread who queries cpu to single cpu
    @note: nc -q
    '''
    cmd = 'TIDS=$( cat {}/utils/qemu.exe | nc -q 1 localhost {}  2>&1 | tee tmp.txt > /dev/null & sleep 0.1;\
 cat tmp.txt | tail -n 1 | jq -r ".return[].thread_id");\
rm -f tmp.txt;\
echo $TIDS;'.format(CONFIG['global']['path']['src'], port)
    cmd_res = subprocess_cmd(cmd)
    for i, tid in enumerate(cmd_res.split(' ')):
        cmd = "sudo taskset -cp {} {};".format(argv[i], tid)
        subprocess_cmd(cmd)


# %%==================================================
# create base image

def install_vpp():
    '''
    install vpp packages
    '''
    if VERBOSE:
        print(">> Install vpp...")
    cmd = "#!/bin/bash\n\
sudo chroot {}/ /bin/bash << EOF\n\
dpkg -i /home/cisco/libvppinfra_*.deb\n\
dpkg -i /home/cisco/vpp_*.deb\n\
dpkg -i /home/cisco/vpp-dbg_*.deb\n\
apt -y remove vpp-dev\n\
dpkg -i /home/cisco/libvppinfra-dev_*.deb\n\
dpkg -i /home/cisco/vpp-dev_*.deb\n\
dpkg -i /home/cisco/vpp-api-python_*.deb\n\
dpkg -i /home/cisco/vpp-plugin-dpdk_*.deb\n\
dpkg -i /home/cisco/vpp-plugin-core_*.deb\n\
dpkg -i /home/cisco/python3-vpp-api_*.deb\n\
service vpp disable\n\
update-rc.d vpp remove\n\
echo --------------------------------\n\
echo +++ Check installed packages +++\n\
apt list --installed | grep vpp\n\
exit\n\
EOF".format(LOOP_DIR)

    filename = os.path.join(CONFIG['global']['path']['tmp'], "install_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)

    subprocess_cmd("sudo chmod +x {}".format(filename))
    subprocess_cmd("sudo bash {}".format(filename))
    subprocess_cmd("sudo rm -f {}".format(filename))
    if VERBOSE:
        print(">> Install vpp done!")


def build_vpp(vpp_dir):
    '''
    build vpp packages
    '''
    if VERBOSE:
        print(">> Install vpp...")
    cmd = "#!/bin/bash\n\
cd {}\n\
make build\n\
".format(vpp_dir)

    filename = os.path.join(CONFIG['global']['path']['tmp'], "build_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)
    res = subprocess_cmd("bash {}".format(filename))
    assert "[vpp-build] Error" not in res, "Error building vpp"

    cmd = "#!/bin/bash\n\
cd {}\n\
make pkg-deb\n\
".format(vpp_dir)

    filename = os.path.join(CONFIG['global']['path']['tmp'], "build_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)
    res = subprocess_cmd("bash {}".format(filename))

    subprocess_cmd(" rm -f {}".format(filename))
    if VERBOSE:
        print(">> Install vpp done!")


def create_base_image():
    '''
    - mount base image
    - copy custom files from backup dir
    - copy vpp debs
    - install vpp
    - [install vpp plugins]
    - remove deb files
    - cleanup (unmount)
    '''
    # make sure there is no mounted image
    umount_image()
    # mount base image
    mount_new_image(CONFIG['global']['path']['orig_img'],
                    CONFIG['global']['path']['base_img'].replace(
                        'base', common.LB_METHODS[LB_METHOD]['img_id']+'-base'))
    # copy vpp debs
    copy_files(os.path.join(CONFIG['global']['path']['vpp'], '*.deb'),
               os.path.join(LOOP_DIR, "home/cisco/"))
    # copy vpp plugins
    copy_files(os.path.join(CONFIG['global']['path']['vpp'], '*.so'),
               os.path.join(LOOP_DIR, "usr/lib/vpp_plugins/"))

    # update /etc/gai.conf so that it will be easier to install stuffs
    filename = os.path.join(LOOP_DIR, 'etc/gai.conf')
    write2file_tee('precedence ::ffff:0:0/96  100',
                   filename, attach_mode=False)

    # update /etc/gai.conf so that it will be easier to install stuffs
    filename = os.path.join(LOOP_DIR, 'home/cisco/lb_method')
    write2file_tee(LB_METHOD,
                   filename, attach_mode=False)

    # install vpp plugins
    install_vpp()
    # remove deb files
    cmd = "sudo rm {}/home/cisco/*.deb".format(LOOP_DIR)
    subprocess_cmd(cmd)
    # cleanup
    umount_image()


# %%==================================================
# nodes

class Node():
    '''
    father class
    '''

    def __init__(self, **kwargs):
        self.__dict__.update({k: v for k, v in kwargs.items()})
        self.backup_dir = os.path.join(CONFIG['global']['path']['src'], self.node_type)

    def mount_new_image(self):
        '''
        branch a new image from base image
        '''
        umount_image()  # make sure there is no mounted image
        mount_new_image(CONFIG['global']['path']['base_img'].replace(
            'base', common.LB_METHODS[LB_METHOD]['img_id']+'-base'), self.img)

    def mount_image(self):
        '''
        mount image of this node
        '''
        if os.path.isfile(self.img):  # if image file exists
            mount_image(self.img)
        else:
            warnings.warn('Image {:s} does not exist.'.format(
                self.img), FileNotExistWarning)

    def umount_image(self):
        '''
        umount image
        '''
        umount_image()

    def update_file(self, content, filename, attach=False):
        '''update a file'''
        filename = LOOP_DIR + filename
        write2file_tee(content, filename, attach_mode=attach)

    def copy_file(self, src, dst, isfolder=False):
        '''copy file'''
        dst = LOOP_DIR + dst
        copy_files(src, dst, isfolder=isfolder)

    def create_folder(self, folder_dir):
        '''create a folder'''
        cmd = "sudo mkdir {}/{}".format(LOOP_DIR, folder_dir)
        subprocess_cmd(cmd)

    def create_folder_ssh(self, folder_dir):
        '''create a folder via ssh'''
        cmd = "ssh -t -t -i ~/.ssh/id_rsa cisco@localhost -p {} \"sudo mkdir {}\"".format(
            self.ssh_port, folder_dir)
        subprocess_cmd(cmd)

    def update_file_ssh(self, content, filename, attach=False):
        '''update file via ssh'''
        # just to make sure that the content doesn't mess up with the cmd
        assert not '"' in content or not "'" in content
        if attach:
            attach = '-a '
        else:
            attach = ''
        cmd = 'ssh -t -t -i ~/.ssh/id_rsa cisco@localhost -p {} \
               "echo \'{}\' | sudo tee {}{} > /dev/null"'.format(
                   self.ssh_port,
                   content,
                   attach,
                   '~/{}'.format(filename))
        subprocess_cmd(cmd)

    def copy_file_scp(self, src, dst, isfolder=False):
        '''copy file via scp'''
        r_placeholder = ' '
        if isfolder:
            r_placeholder = ' -r '
        cmd = 'scp -i ~/.ssh/id_rsa -oStrictHostKeyChecking=no -P {}{}{} cisco@localhost:{} ;'.format(
            self.ssh_port, r_placeholder, src, '~/{}'.format(dst))
        subprocess_cmd(cmd)

    def execute_cmd_ssh(self, cmd, shell=False):
        '''execute cmd locally via ssh'''
        cmd = 'ssh -t -t -i ~/.ssh/id_rsa cisco@localhost -p {} "{}"'.format(
            self.ssh_port,
            cmd)
        if shell:
            return subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=shell)
        else:
            return subprocess_cmd(cmd)


    def update_files_univ(self):
        '''update universal files for all the nodes'''
        # update /etc/network/interfaces
        _content = "# This file describes the network interfaces available on your system\n\
# and how to activate them. For more information, see interfaces(5).\n\
\n\
source /etc/network/interfaces.d/*\n\
\n\
# The loopback network interface\n\
auto lo\n\
iface lo inet loopback\n\
\n\
# The primary network interface\n\
auto eth0\n\
iface eth0 inet dhcp\n\
\n\
# Out-of-band management interface\n\
auto eth1\n\
iface eth1 inet static\n\
address {}\n\
netmask 24\n\
\n".format(self.mgmt_ip)
        if not self.isvpp:
            _content += "# Data-plane interface\n\
auto eth2\n\
iface eth2 inet static\n\
address {0}\n\
netmask {1}\n\
".format(self.ip4_list[0], self.sn4_list[0])
            ip_list = self.ip4_list[1:] + self.ip6_list
            sn_list = self.sn4_list[1:] + self.sn6_list
            for ip_, sn_ in zip(ip_list, sn_list):
                _content += "up ifconfig eth2 add {}/{}\n".format(ip_, sn_)
        self.update_file(_content, '/etc/network/interfaces')

        # update /etc/hostname
        _content = self.hostname
        self.update_file(_content, '/etc/hostname')

        # update /etc/hosts
        _content = "127.0.0.1       localhost\n\
# 127.0.1.1       {}\n\
\n\
# The following lines are desirable for IPv6 capable hosts\n\
::1     localhost ip6-localhost ip6-loopback\n\
ff02::1 ip6-allnodes\n\
ff02::2 ip6-allrouters".format(self.hostname)
        self.update_file(_content, '/etc/hosts')

        # create /home/cisco/init.sh
        _content = "#!/bin/bash\n\
#sudo ntpdate ntp.esl.cisco.com\n"

        self.update_file(_content, '/home/cisco/init.sh')
        # make scripts executable
        cmd = "sudo chmod +x {}/home/cisco/*.sh".format(LOOP_DIR)
        subprocess_cmd(cmd)

    def update_files_vpp(self):
        '''update vpp files'''
        if self.isvpp:
            # create /etc/vpp/startup.conf
            _content = "unix {\n\
nodaemon\n\
log /tmp/vpp.log\n\
full-coredump\n\
cli-listen /run/vpp/cli.sock\n\
startup-config /home/cisco/vpp.startup\n\
}\n\
\n\
api-trace {\n\
on\n\
}\n\
\n\
dpdk {\n\
socket-mem 1024\n\
}"

            self.update_file(_content, '/etc/vpp/startup.conf')

            # create /home/cisco/vpp.startup
            ip_list = self.ip4_list + self.ip6_list
            sn_list = self.sn4_list + self.sn6_list
            _content = ''
            for ip_, sn_ in zip(ip_list, sn_list):
                _content += 'set int ip addr GigabitEthernet0/5/0 {0}/{1}\n'.format(
                    ip_, sn_)
            _content += 'set interface promisc off GigabitEthernet0/5/0\n\
set interface state GigabitEthernet0/5/0 up\n\
ip6 nd GigabitEthernet0/5/0 ra-suppress\n\n'
            self.update_file(_content, '/home/cisco/vpp.startup')
        else:
            pass

    def bootstrap_univ(self):
        '''bootstrap universal files'''
        self.update_files_univ()
        self.update_files_vpp()

    def get_qemu_cmd(self, graphic='-nographic'):
        '''obtain qemu command that confiugre the kvms'''
        # configure the eth0 as a management interface (NAT device)
        res = " -device virtio-net-pci,netdev=nat,bus=pci.0,addr=3.0 \
-netdev user,id=nat,hostfwd=tcp::{:d}-:22".format(
    self.ssh_port)
        # configure the eth1 as an out-of-band interface (bind it to the management bridge)
        res += " -device virtio-net-pci,netdev=mgmt,bus=pci.0,addr=4.0,mac={} \
-netdev tap,id=mgmt,vhost=on,ifname={},script=/bin/true".format(
    self.l2_list[0], self.tap_list[0])
        # configure the remaining interfaces (which will be used by VPP) as supplied in the argument
        for i, addr in enumerate(self.l2_list[1:]):
            res += " -device virtio-net-pci,netdev=net{0},bus=pci.0,addr={1}.0,mac={2} \
-netdev tap,id=net{0},vhost=on,ifname={3},script=/bin/true".format(
    i, i+5, addr, self.tap_list[i+1])
        # final touch
        res = "sudo qemu-system-x86_64 -enable-kvm -cpu host -smp {3} -qmp tcp:localhost:1{0},\
server,nowait -m 4096 -drive file={1},cache=writeback,if=virtio {2}".format(
    self.ssh_port,
    self.img,
    "-k en" if graphic != "-nographic" else "-nographic",
    len(self.vcpu_list)) + res
        return res

    def run(self):
        '''spin up vm with qemu and pin cpu to specific two'''
        def qemu_run(cmd):
            subprocess.Popen(cmd, shell=True)
            time.sleep(3)
            pin_qemu(10000+self.ssh_port, *self.vcpu_list)
            time.sleep(1)
            pin_qemu(10000+self.ssh_port, *self.vcpu_list)
        tap_up(self.tap_list)
        cmd = self.get_qemu_cmd()
        qemu_run(cmd)
        print('{} ready: ssh -p {} cisco@localhost'.format(self.hostname, self.ssh_port))

    def poweroff(self):
        '''poweroff the vm'''
        cmd = 'ssh -i ~/.ssh/id_rsa -oStrictHostKeyChecking=no -t cisco@localhost -p {} "sudo poweroff" 2> /dev/null'.format(
            self.ssh_port)
        subprocess_cmd(cmd)

    def shutdown(self):
        '''shutdown the vm including the net interfaces'''
        self.poweroff()
        time.sleep(5)
        tap_down(self.tap_list)

    def create_img(self):
        '''create the node image'''
        self.mount_new_image()
        self.bootstrap()
        self.umount_image()



class lbNode(Node):
    '''
    lb node class
    '''

    def __init__(self, conf_dict):
        '''initialize node'''
        super().__init__(**conf_dict)

    def __copy_script(self):
        '''copy the necessary scripts to the node'''
        for file in [
                'gt_socket_check.py',
                'shm_proxy.py',
                'env.py',
                'log_usage.py'] + self.files2copy:
            super().copy_file(
                os.path.join(self.backup_dir, file), os.path.join('/home/cisco', file))
        super().copy_file(
            os.path.join(
                self.backup_dir, common.LB_METHODS[LB_METHOD]['version'], 'shm_layout.json'),
            os.path.join('/home/cisco', 'shm_layout.json')
        )
        super().update_file(
            self.init_file_content, '/home/cisco/init.sh', attach=True)

    def __bootstrap_local(self):
        '''update /home/cisco/vpp.startup & config gre tunnel'''
        _content = ''
        for i in range(len(self.as_list)):
            _content += "create gre tunnel src {0} dst {1}\n\
set int state gre{2:d} up\n\
set int ip address gre{2:d} {3}/24\n\
create gre tunnel src {4} dst {5}\n\
set int state gre{6:d} up\n\
set int ip address gre{6:d} {7}/64\n\n\
".format(self.ip4_list[0], self.as_ip4_list[i], 2*i, self.gre4_list[i],
         self.ip6_list[0], self.as_ip6_list[i], 2*i+1, self.gre6_list[i])
        # config lb
        _content += "lb conf ip6-src-address {0}\n\
lb vip {1}/64 encap gre6 new_len 64\n\
lb as {1}/64 {2}\n\n\
".format(self.ip6_list[0], self.vip6, ' '.join(self.as_ip6_list))
        # config route for v4
        for clt_ip, er_ip in zip(self.clt_ip4_list, self.er_ip4_list):
            _content += 'ip route add {}/32 via {} GigabitEthernet0/5/0\n'.format(
                clt_ip, er_ip)
        super().update_file(
            _content, '/home/cisco/vpp.startup', attach=True)
        self.__copy_script()

        # create a folder to store some other results
        super().create_folder('/home/cisco/log')

    def gather_usage(self, clib_log=False):
        '''collect node resource usage with log_usage.py'''
        if clib_log:
            # cmd = 'ssh -t -p {} cisco@localhost "sudo python3 log_usage.py -c &"'.format(
            #     self.ssh_port)
            cmd = "sudo python3 log_usage.py -c"
        else:
            cmd = 'sudo python3 log_usage.py'
        self.execute_cmd_ssh(cmd, shell=True)

    def gt_socket_check(self, n_server):
        '''run init.sh script in the background'''
        cmd = 'ssh -t -p {} cisco@localhost "sudo python3 gt_socket_check.py {}"'.format(
            self.ssh_port, n_server)
        log = subprocess_cmd(cmd)[1:-1]
        if len(log) > 0:
            return [int(i) for i in log.split(',')]
        else:
            return []

    def run_init_bg(self, gather_usage=True, clib_log=False):
        if gather_usage:
            self.gather_usage(clib_log=clib_log)
        cmd = 'ssh -t -p {} cisco@localhost "bash init.sh"'.format(
            self.ssh_port)
        subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)

    def fetch_result(self, dir_, episode, filename='log', isfolder=True):
        '''
        @brief:
            scp results from LB node to host, store at ${dir_}/shm.csv
        @patams:
            dir_: directory to store file
        '''
        r_placeholder = ' '
        if isfolder:
            r_placeholder = ' -r '
        cmd = 'scp -i ~/.ssh/id_rsa -oStrictHostKeyChecking=no -P {0}{1}cisco@localhost:~/{3} \
{2}/{4}_{3}_ep{5};'.format(
    self.ssh_port, r_placeholder, dir_, filename, self.id, episode)
        subprocess_cmd(cmd)

    def bootstrap(self):
        '''bootstrap'''
        super().bootstrap_univ()
        self.__bootstrap_local()

    def create_img(self):
        '''create image of the node'''
        super().mount_new_image()
        self.bootstrap()
        super().umount_image()

class asNode(Node):
    '''
    application server node class
    '''

    def __init__(self, conf_dict):
        super().__init__(**conf_dict)

    def __bootstrap_local(self):
        # update /etc/network/interfaces
        # config gre tunnel
        _content = ''
        for i in range(len(self.lb_list)):
            _content += "# config gre int for lb {0}\n\
auto gre{1}\n\
iface gre{1} inet static\n\
address {2}\n\
netmask 24\n\
pre-up ip tunnel add gre{1} mode gre local {3} remote {4} ttl 255\n\
post-down ip tunnel del gre{1}\n\
\n\
# config gre6 int for lb {0}\n\
up ip -6 tunnel add gre{5} mode ip6gre local {6} remote {7} ttl 255 encaplimit none\n\
up ip link set gre{5} up\n\
up ip -6 addr add {8}/64 dev gre{5}\n\
post-down ip -6 tunnel del gre{5}\n\n\
".format(i, 2*i+1, self.vip4, self.ip4_list[0], self.lb_ip4_list[i],
         2*i+2, self.ip6_list[0], self.lb_ip6_list[i], self.vip6)
        _content += ''  # config client route\n'
        for ip4 in self.clt_ip4_list:
            _content += 'up ip route add {}/32 dev gre1\n'.format(ip4)
        for ip6 in self.clt_ip6_list:
            _content += 'up ip -6 route add {}/128 dev eth2\n'.format(ip6)
        super().update_file(
            _content, '/etc/network/interfaces', attach=True)

        # get ground truth gatherer
        super().copy_file(
            os.path.join(self.backup_dir, 'shmlog'), '/home/cisco/shmlog')
        super().copy_file(
            os.path.join(self.backup_dir, 'shm_server.py'), '/home/cisco/shm_server.py')
        super().update_file(
            '[ -z \`pgrep shmlog\` ] && sudo /home/cisco/shmlog {0} & sleep 1.5\n\
sudo python3 /home/cisco/shm_server.py\n'.format(self.id), '/home/cisco/init.sh', attach=True)

        # put asid into a file
        super().update_file(
            '{}'.format(self.id), '/home/cisco/asid', attach=False)

    def bootstrap(self):
        '''bootstrap'''
        super().bootstrap_univ()
        self.__bootstrap_local()

    def create_img(self):
        '''create image of the node'''
        super().mount_new_image()
        self.bootstrap()
        super().umount_image()

    def run(self):
        '''run the node'''
        super().run()
        time.sleep(10)
        self.init()

    def init(self):
        cmd = 'ssh -t -p {} cisco@localhost "sudo service vpp stop;\
sudo bash ./init.sh" 2> /dev/null'.format(self.ssh_port)
        subprocess.Popen(cmd, shell=True)

class erNode(Node):
    '''
    edge router node class
    '''

    def __init__(self, conf_dict):
        super().__init__(**conf_dict)

    def __bootstrap_local(self):
        # update /home/cisco/vpp.startup
        # config gre tunnel
        _content = ''
        # add route
        for ip4 in self.lb_ip4_list:
            _content += 'ip route add {}/32 via {} {}\n'.format(
                self.vip4, ip4, 'GigabitEthernet0/5/0')  # v4
        for ip6 in self.lb_ip6_list:
            _content += 'ip route add {}/128 via {} {}\n'.format(
                self.vip6, ip6, 'GigabitEthernet0/5/0')  # v6
        super().update_file(
            _content, '/home/cisco/vpp.startup', attach=True)

    def bootstrap(self):
        '''bootstrap'''
        super().bootstrap_univ()
        self.__bootstrap_local()

    def create_img(self):
        '''create image of the node'''
        super().mount_new_image()
        self.bootstrap()
        super().umount_image()


class cltNode(Node):
    '''
    client node class
    '''

    def __init__(self, conf_dict):
        super().__init__(**conf_dict)

    def __bootstrap_local(self):
        # update /etc/network/interfaces
        # config gre tunnel
        _content = '# config ip route\n'
        for ip4 in self.er_ip4_list:
            _content += 'up ip route add {0}/32 via {1} dev eth2\n'.format(
                self.vip4, ip4)
        for ip6 in self.er_ip6_list:
            _content += 'up ip -6 route add {0}/128 via {1} dev eth2\n'.format(
                self.vip6, ip6)

        super().update_file(
            _content, '/etc/network/interfaces', attach=True)
        super().copy_file(
            os.path.join(self.backup_dir, 'replay_fork_io.py'), '/home/cisco/replay.py')
        super().copy_file(
            os.path.join(self.backup_dir, 'run_clt.sh'), '/home/cisco/run_clt.sh')

    def run(self):
        '''run the node'''
        super().run()
        cmd = 'ssh -t -p {} cisco@localhost "sudo service vpp stop;"'.format(
            self.ssh_port)
        subprocess.Popen(cmd, shell=True)

    def start_traffic(self, get_bg=False):
        '''start running input traffic'''
        cmd = 'ssh -t -t cisco@localhost -p {} "sudo python3 replay.py \
trace.csv > trace.log"'.format(self.ssh_port)
        if get_bg:
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess_cmd(cmd)

    def fetch_result(self, dir_, episode):
        '''
        @brief:
            scp results from Client node to host, store at ${dir}/trace.log
        @patams:
            dir: directory to store file
        '''
        cmd = 'scp -i ~/.ssh/id_rsa -oStrictHostKeyChecking=no -P {} \
cisco@localhost:~/trace.log {}/trace.log;'.format(
    self.ssh_port, dir_)
        subprocess_cmd(cmd)
        hostname = subprocess_cmd('hostname -I').split(' ')[0]
        if hostname != common.COMMON_CONF['net']['base_ip']:
            cmd = 'scp -oStrictHostKeyChecking=no {0}/trace.log yzy@{1}:\
{0}/trace_ep{2}.log;'.format(dir_, common.COMMON_CONF['net']['base_ip'], episode)
            subprocess_cmd(cmd)

    def bootstrap(self):
        '''bootstrap'''
        super().bootstrap_univ()
        self.__bootstrap_local()

    def create_img(self):
        '''create image of the node'''
        super().mount_new_image()
        self.bootstrap()
        super().umount_image()

# %%==================================================
'''
higher-level function
'''


def get_config(filename):
    global CONFIG
    '''
    load config file for all nodes (generated by ${root}/src/utils/gen_conf.py)
    Note: this should be the first function to call
    @params:
        filename
    '''
    conf_file = os.path.join(common.COMMON_CONF['dir']['root'], 'config', 'cluster', filename)
    if not os.path.isfile(conf_file):  # if config file doesn't exist
        warnings.warn(
            'Config {} does not exist, create w/ default config.'.format(conf_file),
            FileNotExistWarning)
    CONFIG = common.json_read_file(conf_file)


def get_nodes(lb_method, node_config=None):
    '''
    get node instances given configuration
    @params:
        node_config - configuration for different kinds of nodes
                      (default = None and load global CONF as config)
                    e.g.:
        {'dev': [{'id': 0,
                    ...
                }],
        'clt': [{'id': 0,
                    ...
                }],
        'er': [{'id': 0,
                    ...
                }],
        'lb': [{'id': 0,
                    ...
                }],
        'as': [{'id': 0,
                    ...
                },
                {'id': 1,
                    ...
                }]}
    '''
    global NODES
    # refresh common.LB_METHODS just in case of some updates
    filename = os.path.join(DIRNAME, '../../config/lb-methods.json')
    common.LB_METHODS = common.json_read_file(filename)

    if not node_config:
        node_config = CONFIG['nodes']
    nodes = {}
    for k in node_config.keys():
        nodes[k] = []
        for node in node_config[k]:
            if k == 'lb':  # for LB nodes, add files to copy
                node['files2copy'] = common.LB_METHODS[lb_method]['files']
                node['init_file_content'] = '\n'.join(
                    common.LB_METHODS[lb_method]['init_lines'])
            nodes[k].append(eval(k+'Node')(node))
    NODES = nodes
    if VERBOSE:
        print("NODES updated:" + str(NODES))
    return nodes


def rebuild(nodes=None, from_orig=False):
    '''
    rebuild images for given nodes
    @params:
        nodes - a dictionary of node instances generated from get_nodes()
                (default = None and load global NODES)
        from_orig - whether or not rebuild base image (default = False)
    '''
    if not nodes:
        nodes = NODES
    if from_orig:
        create_base_image()
    for k in nodes.keys():
        for node in nodes[k]:
            node.create_img()


def host_br_up(nodes=None):
    '''
    setup bridge on the host side
    @params:
        nodes - a dictionary of node instances generated from get_nodes()
                (default = None and load global NODES)
    '''
    if not nodes:
        nodes = NODES
    # bring up bridges
    br_up()
    # get all tap interfaces (respectively for vpp and mgmt)
    tapvpp = []
    tapmgmt = []
    for k in nodes.keys():
        for node in nodes[k]:
            for tap in node.tap_list:
                if 'vpp' in tap:
                    tapvpp.append(tap)
                elif 'mgmt' in tap:
                    tapmgmt.append(tap)
    cmd = ''
    for tap in tapvpp:
        cmd += 'sudo brctl addif {0} {1};'.format(
            CONFIG['global']['net']['bridge'], tap)
    for tap in tapmgmt:
        cmd += 'sudo brctl addif {0} {1};'.format(
            CONFIG['global']['net']['mgmt_bridge'], tap)
    subprocess_cmd(cmd)


def runall(nodes=None):
    '''
    run all the nodes
    @params:
        nodes - a dictionary of node instances generated from get_nodes()
                (default = None and load global NODES)
    '''
    umount_image()
    if not nodes:
        nodes = NODES
    for k in nodes.keys():
        for node in nodes[k]:
            node.run()
    host_br_up()


def shutall(nodes=None):
    '''
    shutdown all the nodes
    '''
    if not nodes:
        nodes = NODES
    tap_ifs = []
    for k in nodes.keys():
        for node in nodes[k]:
            node.poweroff()
            tap_ifs += node.tap_list
    time.sleep(5)
    tap_down(tap_ifs)
    br_down()


def gt_socket_check(nodes=None):
    '''
    check ground truth gathering socket connection
    '''
    if not nodes:
        nodes = NODES
    for lb in nodes['lb']:
        err = lb.gt_socket_check(len(lb.as_list))
        while len(err) > 0:
            print("LB Node {}: found error socket with server {}".format(lb.id, err))
            time.sleep(1)
            for i in err:
                nodes['as'][i].init()
            err = lb.gt_socket_check(len(lb.as_list))
        print("LB Node {}: pass".format(lb.id))
    if VERBOSE:
        print("GT socket check pass.")


def get_task_name_dir(experiment, trace, lb_method, sample, alias=None):
    '''
    @brief:
        initialize task name and corresponding directory to store results
    @params:
        experiment: name of the high-level set of experiments
        trace: type of the networking trace to be replayed
        lb_method: name of the load balancing method
        sample: sample of the chosen type of trace
    @return:
        task_name: name of the task
        task_dir: directory to store experiment result for this task
    '''
    assert lb_method in common.LB_METHODS.keys()
    # set task name
    task_name = sample.rstrip(".csv")
    if alias:
        task_name += '-{}'.format(alias)
    task_dir = os.path.join(common.COMMON_CONF['dir']['root'], 'data',
                            'results', experiment, trace, lb_method, task_name)
    task_name = '-'.join([trace, lb_method, task_name])
    return task_name, task_dir


def init_task_info(
        experiment,
        lb_method,
        trace,
        sample,
        cluster_config,
        alias=None
    ):
    '''
    @brief:
        initialize configuration info w/ arguments
        setup task name
        setup directories to store experiment results w/ format:
            `${root}/data/results/${trace}/${lb_method}/${task}+${alias}/`
        setup node configuration for the cluster
    @params:
        experiment: name of the experiment that may comprise many tests under
                    a specific configuration
        lb_method: name of the load balancing method
        trace: type of the networking trace to be replayed
        sample: sample of the chosen type of trace
        cluster_config: json configuration file of server cluster
    @return:
        task_name: name of the task
        task_dir: directory to store experiment result for this task
        nodes: configuration for all the nodes
    '''
    global LB_METHOD
    assert lb_method in common.LB_METHODS.keys()
    LB_METHOD = lb_method
    root_dir = common.COMMON_CONF['dir']['root']
    result_dir = os.path.join(root_dir, 'data', 'results')
    experiment_dir = os.path.join(result_dir, experiment)
    trace_dir = os.path.join(experiment_dir, trace)
    method_dir = os.path.join(trace_dir, lb_method)
    task_name, task_dir = get_task_name_dir(
        experiment, trace, lb_method, sample, alias)

    # create folders if not yet existed
    dir2make = [result_dir, experiment_dir, trace_dir, method_dir, task_dir]
    common.create_folder(dir2make)

    # get cluster config
    assert os.path.exists(os.path.join(root_dir, 'config', 'cluster', cluster_config))
    # load config
    get_config(cluster_config)
    nodes = get_nodes(lb_method)

    # update shm_layout.json
    shm_layout = common.json_read_file(os.path.join(
        common.COMMON_CONF['dir']['root'],
        'src',
        'lb',
        common.LB_METHODS[lb_method]['version'],
        'shm_layout_base.json'))
    shm_layout.update({
        'meta': {
            'n_as': CONFIG['global']['topo']['n_node']['as'],
            'weights': CONFIG['global']['topo']['n_vcpu']['as']
        }
    })
    common.json_write2file(shm_layout, os.path.join(
        common.COMMON_CONF['dir']['root'],
        'src',
        'lb',
        common.LB_METHODS[lb_method]['version'],
        'shm_layout.json'))

    return task_name, task_dir, nodes


#--- Pipeline ---#


def prepare_img(lb_method, from_orig=None):
    '''
    @brief:
        prepare all the image files
    @params:
        lb_method: name of the load balancing method
        from_orig
    '''

    assert lb_method in common.LB_METHODS.keys()
    root_dir = common.COMMON_CONF['dir']['root']
    vpp_dir = os.path.join('/', 'root', 'vpp')

    if from_orig is None:  # if `from_orig` is not specified here
        if os.path.exists(CONFIG['global']['path']['base_img'].replace(
                'base', common.LB_METHODS[lb_method]['img_id']+'-base')):
            from_orig = False
        else:
            from_orig = True
            print("base img for {} does not exist, create one...".format(lb_method))

    if from_orig:
        # build vpp
        cmd = 'python3 {} -m {}'.format(os.path.join(root_dir,
                                                     'src', 'vpp', 'gen_layout.py'), lb_method)
        subprocess_cmd(cmd)
        # copy generated lb files to vpp folder
        cmd = 'cp -r {} {}/src/plugins/'.format(
            os.path.join(root_dir, 'src', 'vpp', common.LB_METHODS[lb_method]['version'], 'lb'), vpp_dir)
        subprocess_cmd(cmd)
        build_vpp(vpp_dir)
        cmd = 'cp {}/build-root/*.deb {}/data/vpp_deb/'.format(
            vpp_dir, root_dir)
        subprocess_cmd(cmd)
        cmd = 'cp {}/build-root/build-vpp-native/vpp/lib/vpp_plugins/lb_plugin.so \
{}/data/vpp_deb/'.format(vpp_dir, root_dir)
        subprocess_cmd(cmd)
        LB_METHOD_LAST_BUILD = lb_method

    umount_image()
    rebuild(from_orig=from_orig)


def prepare_trace_sample(trace, sample, clip_n=None):
    '''
    @brief:
        scp trace sample files to client node
    @params:
        trace: type of the networking trace to be replayed
        sample: sample of the chosen type of trace
        clip_n: set a number if we want to clip off some lines and use only first ${clip_n} lines
    '''
    sample_file_dir = os.path.join(CONFIG['global']['path']['trace'], trace, sample)
    print(">> prepare trace sample:", sample_file_dir)
    if not os.path.exists(sample_file_dir):
        print("ERROR: sample does not exist:", sample_file_dir)
        return
    NODES['clt'][0].copy_file_scp(sample_file_dir, "sample.csv")
    if clip_n:
        cmd = 'ssh -t -t -i ~/.ssh/id_rsa cisco@localhost -p 8800 "head -n {} sample.csv > trace.csv;\
rm -f sample.csv"'.format(clip_n)
        subprocess_cmd(cmd)
    else:
        cmd = 'ssh -t -t -i ~/.ssh/id_rsa cisco@localhost -p 8800 "mv sample.csv trace.csv"'
        subprocess_cmd(cmd)
