# Runners-metrics-exporter

Script that receives the number of VMs per folder from the Yandex.Cloud API. Script selects VMs that have a certain substring in their name.  
In our case, it is used to monitor the number of gitlab-runners for each project (folder).  
Then it issues metrics in the Prometheus format.  
Script currently using Python 3.6.  

## Table of content

- [Where using](#where-using)
- [Quickstart](#quickstart)
  - [Required variables](#required-variables)
  - [Run in k8s](#run-in-k8s)
  - [Run locally](#run-locally)
- [TODO](#todo)

## Where using

In itlabs.io, we use a bundle to implement gitlab-runners for different businesses/projects:

- gitlab-runner (<https://docs.gitlab.com/runner/>);
- docker-machine (<https://github.com/docker/machine>);
- docker-machine-driver-yandex (<https://github.com/yandex-cloud/docker-machine-driver-yandex>).  

The scheme is that runners with the docker-machine executor are registered in gitlab-runner, which communicates with the Yandex.Cloud API through the docker-machine-driver-yandex plugin and creates a new VM for each job in GitLab in the business/project folder with given parameters. After the job is completed, the VM is destroyed. This allows you to significantly reduce costs and separate them between businesses/projects. The naming of the VM is arranged according to the same principle and always has the substring "runner" in the name. This script helps to see the number of running VMs used as runners at any given time.

## Quickstart

### Required variables

- **CLOUD_ID** - ID of the cloud where your folder/folders are located;
- **SERVICE_ACCOUNT_ID** - SA in Yandex.Cloud, which has viewer rights in all folders from which you are going to collect information;
- **KEY_ID** - the ID of the authorized key generated for the SA that is used to obtain the IAM token;
- **SCRAPE_TIMEOUT** - period in seconds after which the script will request the number of VMs in folders;
- **TOKEN_TTL** - lifetime of the received IAM token in seconds. After the specified period of time, the token will be re-requested.

### Run in k8s

Manifest of the secret with parameters:

```yaml
---
apiVersion: v1
data:
  cloud_id: "CLOUD_ID encoded base64"
  key_id: "KEY_ID encoded base64"
  service_account_id: "SERVICE_ACCOUNT_ID encoded base64"
  private_key: "the private key encoded base64"
kind: Secret
metadata:
  name: runners-metrics-exporter-config
  namespace: monitoring
type: Opaque
```

The deployment manifest is in **kubernetes/deployment.yaml**  
The service manifest is in **kubernetes/service.yaml**  
The servicemonitor manifest is in **kubernetes/servicemonitor.yaml**

### Run locally

```bash
git clone git@github.com:itlabsio/runners-metrics-exporter.git
cd runners-metrics-exporter/
python3.6 -m venv env
source env/bin/activate
pip install -U pip
pip install -r requirements.dev.txt
# 1. Set all required variables
# 2. Put the private_key file with the private key from SA Yandex.Cloud into the private_key directory
pytnon3.6 main.py
```

## TODO

- Make several types of metrics for different VM statuses (probably not all statuses will fall):
  - PROVISIONING
  - RUNNING
  - STOPPING
  - STOPPED
  - STARTING
  - RESTARTING
  - UPDATING
  - ERROR
  - CRASHED
- Implement the ability to scrape exporter metrics using a token;
- Add a variable to specify the port where metrics can be scraped;
- Tests.
