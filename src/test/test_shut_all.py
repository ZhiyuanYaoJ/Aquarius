import sys
utils_dir = 'src/utils'
sys.path.insert(0, utils_dir)  # add utils dir to path
import testbed_utils as tu

# initialize params
config = 'sc-ae'
method = 'maglev'
trace = 'wiki'
sample = 'hour0.csv'
ep = 0
experiment = 'unittest'
clip_n = 5000
task_name, task_dir, nodes = tu.init_task_info(
    experiment=experiment,
    lb_method=method,
    trace=trace,
    sample=sample,
    cluster_config='{}.json'.format(config),
    alias=config,
)
# shutdown VMs on kvmp-3 locally
tu.shutall()
