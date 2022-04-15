# Aquarius

> Aquarius - Enabling Fast, Scalable, Data-Driven Virtual Network Functions

## Introduction

This repository implements a data-collection and data-exploitation mechanism Aquarius as a load balancer plugin in VPP. 
For the sake of reproducibility, software and data artifacts for performance evaluation are maintained in this repository.

## Directory Roadmap

```
- config                    // configuration files in json format        
- sc-author-kit-log         // artifacts description of testbed hardware, required by sc21 committee
- src                       // source code
    + client/server         // scripts that run on client/server VMs
    + lb                    // scripts that run on lb VMs
        * dev               // dev version (for offline feature collection and classsification section)
        * deploy            // deploy version (for online policy evaluation and autoscaling/load-balancing section)
        * motivation        // scripts for experiments in the motivation section (Section II - Background)
    + utils                 // utility scripts that help to run the testbed
    + vpp                   // vpp plugin
        * dev               // dev version (for offline feature collection and classsification section)
        * deploy            // deploy version (for online policy evaluation and autoscaling/load-balancing section)
    + test                  // unit test codes
- data                      
    + trace                 // network traces replayed on the testbed
    + results (omitted)     // This is where all the datasets are dumped (will be automatically created once we run experiments)
    + img                   // VM image files (omitted here because of file size, server configurations are documented in README)
```

## Get Started

### Pre-Configuration

Run `python3 setup.py`, which does the following things:
- update the root directory in `config/global_config.json` to the directory of the cloned `aquarius` repository (replace the `/home/yzy/aquarius`);
- clone the VPP repository in `src/vpp/base`;
- update the `physical_server_ip` in `config/global_config.json` to the IP addresses of the actual server IP addresses in use;
- update the `vlan_if` as the last network interface on the local machine
- update the `physical_server_ip` in `config/cluster/unittest-1.json` to the local hostname

The user has to be a sudoer, and to simplify the process and run in notebook, run `sudo visudo` and add `$USER_ID ALL=(ALL:ALL) NOPASSWD: ALL`.

### VM images

To prepare a VM original image, refer to the README file in `data`. To run all the experiments without issues, create a ssh-key on the host servers and copy the public key to the VMs so that commands can be executed from the host using `ssh -t -t`.

### Run example

A simple example is created using a small network topology (1 client, 1 edge router, 1 load balancer, and 4 application servers) on a single machine. 
Simply follow the jupyter notebook in `notebook/unittest`. 
Make sure the configurations are well adapted to your own host machine. Also make sure that the host machine has at least **20** CPUs. 
Otherwise, the configuration can be modified in `config/cluster/unittest-1.json`. 
To reduce the amount of CPUs required, change the number of `vcpu` of each node in the json file.

## Reproducibility

To reproduce the results in Aquarius paper, three notebooks are presented in `notebook/reproduce`. 
The dataset that are generated from the experiments are stored in `data/reproduce`. 
To run these experiments, **4** physical machines with **12** physcial cores (**48** CPUs) each are required. 
MACROs in the notebook should be well adapted. For instance, VLAN should be configured across the actual inerfacesin use. 
An example of network topology is depicted below.

![Multi-server Topology](data/figures/testbed-topo-vlan.png)

### Containerised VM Image

A VM image is created and made available via [this link](https://cisco.box.com/s/ugwsfa1431kx9drgdwwijxkng87vwsxp) for reproducibility.
Based on the original image - downloaded from the previous link to the `data/img` directory (`data/img/origin/lb-vpp.img`), subsidiary images will be created based on different configurations by functions (_e.g._ `create_base_image()` in `src/utils/testbed_utils.py`).
For each setup, the base image is first built based on the original image, then one VM image is created for each network node (_e.g._ client, edge router, load balancer, server).
Since the actual experimental setup requires VLAN configurations among physical servers, an example small-scale experimental setup can be reproduced from the pipeline documented in the jupyter notebook `notebook/unittest/run-example.ipynb`.
We believe that this is the most efficient way to provide artifects for evaluation and reproduction.

### For Motivation Section

Corresponding scripts that were used in the motivation section can be found in `src/lb/motivation`.
The pipeline of producing the experimental results of the motivation section is provided in `notebook/reproduce/motivation.ipynb`.
`baseline.py` is the script that collects and log information.
It calls `env_*.py` which then relies on `shm_proxy.py` to parse the shared memory and communicate with the servers for actively probed server load information.
`env_lower_gt_message.py` and `env_upper_gt_message.py` respectively receives the lowest/highest amount of bytes for the control packets that carry server load information.
The `shm_layout.json` explicitly defines the layout of the shared memory used in this application.

### For Classification Section

Refer to the configuration files in the `config/lb-methods-classification.json/` (rename it to `lb-methods.json` so that it will be loaded by `src/utils/testbed_utils.py`) .
The whole pipeline of producing the experimental results of the classfication section is provided in `notebook/reproduce/classification`.
The shared memory layout of this application is available in `src/lb/dev`.
The overhead benchmark is in part (pcap packet log) achieved by building and running `src/lb/dev/pcap` on the load balancer node.
### For Auto-Scaling Section

Refer to the configuration file `config/lb-methods.json`.
The whole pipeline of producing the experimental results of the auto-scaling section is provided in `notebook/reproduce/auto-scaling`, including offline training and online predicting steps.
The shared memory layout of this application is available in `src/lb/deploy`.
The trained models are stored in `src/lb/autoscale`.

### For Load Balancing Section

Refer to the configuration file `config/lb-methods.json`.
The whole pipeline of producing the experimental results of the load balancing section is provided in `notebook/reproduce/lb/run-and-plot.ipynb`.
The shared memory layout of this application is available in `src/lb/deploy`.
The load balancing policies are stored in `src/lb`.

## Notes

Running the scripts, _e.g._ `src/utils/testbed_utils.py`, requires root access.

### Build and Run Docker

To make the image more easily distributed, we created a script to build a basic docker image along with the VM image.

```sh
./build-docker.sh
```