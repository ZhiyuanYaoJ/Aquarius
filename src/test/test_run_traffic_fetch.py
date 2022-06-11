import time
import sys
utils_dir = '../../src/utils'
sys.path.insert(0, utils_dir)  # add utils dir to path
import testbed_utils as tu

# initialize params
config = 'unittest'
method = 'maglev'
trace = 'wiki'
sample = 'hour0.csv'
ep = 0
experiment = 'unittest'
clip_n = 4000
task_name, task_dir, nodes = tu.init_task_info(
    experiment=experiment,
    lb_method=method,
    trace=trace,
    sample=sample,
    cluster_config='{}.json'.format(config),
    alias=config,
)
# shutdown VMs on kvmp-3 locally
# check management channel between LBs and servers
net_ok = False
while not net_ok:
    try:
        tu.gt_socket_check()
        net_ok = True
    except:
        print('error')
        time.sleep(1)

# start processor agents on LBs
for lb in tu.NODES['lb']:
    lb.run_init_bg()

# prepare network trace
tu.prepare_trace_sample(trace, sample, clip_n=clip_n)

# run traffic
t0 = time.time()
tu.NODES['clt'][0].start_traffic()
print("total time: {:.3f}s".format(time.time()-t0))

# fetch result
for lb in tu.NODES['lb']:
    lb.fetch_result(task_dir, ep)

tu.NODES['clt'][0].fetch_result(task_dir, ep)
