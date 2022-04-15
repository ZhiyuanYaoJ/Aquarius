#!/bin/bash
#sudo ntpdate ntp.esl.cisco.com

sudo python3 log_usage.py &
sudo python3 baseline.py
