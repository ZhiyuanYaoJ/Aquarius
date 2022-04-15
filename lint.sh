#!/bin/bash

pylint src/as/*.py
pylint src/clt/*.py
pylint src/lb/**/*.py
pylint src/utils/common.py
pylint src/utils/run_server.py
pylint src/utils/run_traffic.py
pylint src/utils/shutdown_server.py
