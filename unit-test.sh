#!/bin/bash

python3 setup.py
python3 -m unittest src/test/test_common.py
python3 -m unittest src/test/test_testbed_utils.py
python3 -m unittest src/test/test_gen_cluster_config.py
python3 -m unittest src/test/test_node_agent.py
# python3 -m unittest src/test/test_vpp_build.py
