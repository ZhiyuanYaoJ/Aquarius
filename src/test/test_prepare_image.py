import sys
import os
import time
import warnings
utils_dir = '../../src/utils'
sys.path.insert(0, utils_dir)  # add utils dir to path
import common
# gives us access to global configurations, e.g. what is used as VLAN interface

# %%==================================================
# macro & global variables
CONFIG = {}  # configuration of testbed
NODES = {}  # a dictionary of all node instances of different type
LB_METHOD = 'maglev'
LB_METHOD_LAST_BUILD = 'maglev'

# %%==================================================
# functions

def copy_files(src, dst, isfolder=False, sudoer=True):
    '''
    copy files from src to dst
    @param:
        src/dst: path on the machine
    '''
    if common.VERBOSE:
        print("- Copy from {} to {}...".format(src, dst), end='\r')
    r_placeholder = ' '
    if isfolder:
        r_placeholder = ' -r '
    if sudoer:
        cmd = "sudo cp{}{} {}".format(r_placeholder, src, dst)
    else:
        cmd = "cp{}{} {}".format(r_placeholder, src, dst)
    common.subprocess_cmd(cmd)
    if common.VERBOSE:
        print("- Copy from {} to {} done!".format(src, dst))


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
        cmd = 'sudo echo \"{}" | sudo tee {}{}'.format(
            content, attach, filename)
    else:
        cmd = 'sudo echo \"{}" | sudo tee {}{} > /dev/null'.format(
            content, attach, filename)
    common.subprocess_cmd(cmd)


def mount_new_image(img_orig, img_new):
    '''
    mount new image: img_orig -> img_new
    @param:
        img_orig: original image
        img_new: target
    '''
    if common.VERBOSE:
        print(">> Mounting image: {}...".format(img_new), end='\r')
    cmd = "rm -f {0};\
    qemu-img create -f qcow2 -b {1} {0};\
    sudo modprobe nbd max_part=8;\
    sudo qemu-nbd --connect=/dev/nbd0 {0};\
    sudo mount -o loop /dev/nbd0p1 {2};\n".format(img_new, img_orig, common.LOOP_DIR)
    common.subprocess_cmd(cmd)
    if common.VERBOSE:
        print(">> Mounting image {} done!".format(img_new))


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
    common.umount_image()
    # mount base image
    mount_new_image(CONFIG['global']['path']['orig_img'],
                    CONFIG['global']['path']['base_img'].replace(
                        'base', common.LB_METHODS[LB_METHOD]['img_id']+'-base'))
    # copy vpp debs
    copy_files(os.path.join(CONFIG['global']['path']['vpp'], '*.deb'),
               os.path.join(common.LOOP_DIR, "home/cisco/"))
    # copy vpp plugins
    copy_files(os.path.join(CONFIG['global']['path']['vpp'], '*.so'),
               os.path.join(common.LOOP_DIR, "usr/lib/vpp_plugins/"))

    # update /etc/gai.conf so that it will be easier to install stuffs
    filename = os.path.join(common.LOOP_DIR, 'etc/gai.conf')
    write2file_tee('precedence ::ffff:0:0/96  100',
                   filename, attach_mode=False)

    # update /etc/gai.conf so that it will be easier to install stuffs
    filename = os.path.join(common.LOOP_DIR, 'home/cisco/lb_method')
    write2file_tee(LB_METHOD,
                   filename, attach_mode=False)

    # install vpp plugins
    install_vpp()
    # remove deb files
    cmd = "sudo rm {}/home/cisco/*.deb".format(common.LOOP_DIR)
    common.subprocess_cmd(cmd)
    # cleanup
    common.umount_image()


def install_vpp():
    '''
    install vpp packages
    '''
    if common.VERBOSE:
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
EOF".format(common.LOOP_DIR)

    filename = os.path.join(CONFIG['global']['path']['tmp'], "install_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)

    common.subprocess_cmd("sudo chmod +x {}".format(filename))
    common.subprocess_cmd("sudo bash {}".format(filename))
    common.subprocess_cmd("sudo rm -f {}".format(filename))
    if common.VERBOSE:
        print(">> Install vpp done!")


def build_vpp(vpp_dir):
    '''
    build vpp packages
    '''
    if common.VERBOSE:
        print(">> Install vpp...")
    cmd = "#!/bin/bash\n\
cd {}\n\
make build\n\
".format(vpp_dir)

    filename = os.path.join(CONFIG['global']['path']['tmp'], "build_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)
    res = common.subprocess_cmd("bash {}".format(filename))
    assert "[vpp-build] Error" not in res, "Error building vpp"

    cmd = "#!/bin/bash\n\
cd {}\n\
make pkg-deb\n\
".format(vpp_dir)

    filename = os.path.join(CONFIG['global']['path']['tmp'], "build_vpp.sh")
    with open(filename, "w") as text_file:
        text_file.write(cmd)
    res = common.subprocess_cmd("bash {}".format(filename))

    common.subprocess_cmd(" rm -f {}".format(filename))
    if common.VERBOSE:
        print(">> Install vpp done!")


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
                'lb-', common.LB_METHODS[lb_method]['img_id']+'-')):
            from_orig = False
        else:
            from_orig = True
            print("base img for {} does not exist, create one...".format(lb_method))

    if from_orig:
        # build vpp
        cmd = 'python3 {} -m {}'.format(os.path.join(root_dir,
                                                     'src', 'vpp', 'gen_layout.py'), lb_method)
        common.subprocess_cmd(cmd)
        # copy generated lb files to vpp folder
        cmd = 'cp -r {} {}/src/plugins/'.format(
            os.path.join(root_dir, 'src', 'vpp', common.LB_METHODS[lb_method]['version'], 'lb'), vpp_dir)
        common.subprocess_cmd(cmd)
        build_vpp(vpp_dir)
        cmd = 'cp {}/build-root/*.deb {}/data/vpp_deb/'.format(
            vpp_dir, root_dir)
        common.subprocess_cmd(cmd)
        cmd = 'cp {}/build-root/build-vpp-native/vpp/lib/vpp_plugins/lb_plugin.so \
{}/data/vpp_deb/'.format(vpp_dir, root_dir)
        common.subprocess_cmd(cmd)
        LB_METHOD_LAST_BUILD = lb_method

    common.umount_image()
    rebuild(from_orig=from_orig)


if __name__ == '__main__':
    CONFIG = common.get_config('unittest.json')
    prepare_img('ecmp', from_orig=True)
