import sys
import os
utils_dir = '../../src/utils'
sys.path.insert(0, utils_dir) # add utils dir to path
import testbed_utils as tu
import time

# initialize params
config = 'unittest'
method = 'ecmp'
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
tu.prepare_img(lb_method=method, from_orig=True)
