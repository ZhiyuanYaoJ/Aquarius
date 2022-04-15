# Copyright(c) 2021 Cisco and / or its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http: // www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Common utils for the load balancer testbed
'''
import logging
import sys
import os
import json

def init_logger(filename, logger_name):
    '''
    @brief:
        initialize logger that redirect info to a file just in case
        we lost connection to the notebook
    @params:
        filename: to which file should we log all the info
        logger_name: an alias to the logger
    '''

    # get current timestamp

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(filename=filename),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Test
    logger = logging.getLogger(logger_name)
    logger.info('### Init. Logger {:s} ###'.format(logger_name))

    return logger


def json_write2file(data, filename):
    '''
    @brief:
        write data to json file
    '''
    with open(filename, "w") as file_target:
        # w/ indent the file looks better
        json.dump(data, file_target, indent=4)


def json_read_file(filename):
    '''
    @brief:
        read data from json file
    '''
    with open(filename, "r") as file_target:
        return json.load(file_target)


def write_file(lines, filename):
    '''
    @desc:
        write lines from a list of strings to a file
    @params:
        (str) filename
        (list[str]) lines
    '''
    with open(filename, "w") as file_target:
        for line_ in lines:
            file_target.write("{}\n".format(line_))


def create_folder(dirs):
    '''
    @brief:
        create folder if does not exist
    '''
    for dir_ in dirs:
        if not os.path.exists(dir_):
            os.mkdir(dir_)


def read_file(filename):
    '''
    @desc:   read lines from a file into a list
    @params: (str)filename
    @return: list of strings
    '''
    lines = []
    with open(filename, "r") as myfile:
        lines = [line.rstrip('\n') for line in myfile]
    return lines


DIRNAME_ = os.path.dirname(__file__)
# get common configuration
FILENAME_ = os.path.join(DIRNAME_, '../../config/global_conf.json')
COMMON_CONF = json_read_file(FILENAME_)
# get all LB methods
FILENAME_ = os.path.join(DIRNAME_, '../../config/lb-methods.json')
LB_METHODS = json_read_file(FILENAME_)
