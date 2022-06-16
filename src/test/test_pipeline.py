# # Import dependencies

import time
import sys
import os
utils_dir = 'src/utils'
sys.path.insert(0, utils_dir)  # add utils dir to path
import testbed_utils as tu


# # Initialization
#
# Initialise parameters and configurations for the testbed.


config = 'unittest'
method = 'ecmp-microbench-all'
trace = 'wiki'
sample = 'hour0.csv'
ep = 0
experiment = 'unittest'
clip_n = 10000
task_name, task_dir, nodes = tu.init_task_info(
    experiment=experiment,
    lb_method=method,
    trace=trace,
    sample=sample,
    cluster_config='{}.json'.format(config),
    alias=config,
)


# # Setup environment
#
# Rebuild KVM images from the origin image (`/opt/aquarius/data/img/origin.img`) for all the nodes. Then spin up the KVM instances, along with network configurations.


tu.prepare_img(lb_method=method, from_orig=None)
tu.runall()


# check network connection
net_ok = False
while not net_ok:
    try:
        tu.gt_socket_check()
        net_ok = True
    except:
        print('error')
        time.sleep(1)

# prepare network trace
tu.prepare_trace_sample(trace, sample, clip_n=clip_n)


# # Run experiments

# start processor agents on LBs
for lb in tu.NODES['lb']:
    lb.run_init_bg(clib_log=True)

# run traffic
t0 = time.time()
tu.NODES['clt'][0].start_traffic()
print("total time: {:.3f}s".format(time.time()-t0))

# Fetch results
#
# Once the network traffic is done, gather measurements and logs from both the load balancer node and the client node.

for lb in tu.NODES['lb']:
    lb.execute_cmd_ssh("touch /home/cisco/done")

time.sleep(8)

for lb in tu.NODES['lb']:
    lb.fetch_result(task_dir, ep)

tu.NODES['clt'][0].fetch_result(task_dir, ep)


# # Cleanup
# Once the test finished, cleanup the environment.

tu.shutall()
