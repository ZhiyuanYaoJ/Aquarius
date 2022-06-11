import sys
import os
import subprocess
import time
import warnings

LOOP_DIR = '/mnt/loop'

def subprocess_cmd(command):
    '''
    execute command and print out result
    '''
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    return proc_stdout.decode("utf-8")


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
    cmd = "sudo modprobe nbd max_part=8;\
    sudo qemu-nbd --connect=/dev/nbd0 {};\
    sudo mount -o loop /dev/nbd0p1 {};\
    \n".format(img, LOOP_DIR)
    subprocess_cmd(cmd)

if __name__ == '__main__':
    mount_image('/opt/aquarius/data/img/maglev-base.img')
