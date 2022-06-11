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

def umount_image():
    '''
    cleanup mounted image (umount and disconnect)
    '''
    if os.path.exists('{}/home/cisco'.format(LOOP_DIR)):
        cmd = "sudo chown 1000:1000 {0}/home/cisco/*;\
        sudo umount {0}/;\
        sudo qemu-nbd --disconnect /dev/nbd0;\n".format(LOOP_DIR)
        subprocess_cmd(cmd)

if __name__ == '__main__':
    umount_image()
