"""runners-metrics-exporter"""

import sys
import os
import logging
from logging import StreamHandler, Formatter
import time
from typing import Optional
import jwt
import requests

from prometheus_client import start_http_server, Gauge


API_MAIN_DOMAIN = 'api.cloud.yandex.net/'
CLOUD_ID = os.getenv('CLOUD_ID')
# The service account must have the view role for all the necessary folders
SERVICE_ACCOUNT_ID = os.getenv('SERVICE_ACCOUNT_ID')
KEY_ID = os.getenv('KEY_ID')
# Interval in seconds with which the script will poll
# folders for runners
SCRAPE_TIMEOUT = int(os.getenv('SCRAPE_TIMEOUT'))
# Interval in seconds during which the current IAM token will be used
# after which it re-requests
TOKEN_TTL = int(os.getenv('TOKEN_TTL'))
# Substring to search in VM names
SUBSTRING_IN_VM_NAME = os.getenv('SUBSTRING_IN_VM_NAME')
# List of VM names that will not be taken into account
BLACKLIST_VM_NAMES = list(os.getenv('BLACKLIST_VM_NAMES'))
PORT = int(os.getenv('PORT'))

# Metric settings
metric_runner_up = Gauge('runner_up', 'Runner up now', ['folder_name','folder_id'])

# Logger settings
logger = logging.getLogger('logger')
logger.setLevel(logging.INFO)
handler = StreamHandler(stream=sys.stdout)
handler.setFormatter(Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)


def get_iam_token() -> str:
    """The function of obtaining an IAM token based on an authorized private key.
     https://cloud.yandex.ru/docs/iam/operations/iam-token/create-for-sa#via-jwt
    """

    with open("private_key/private_key", 'r', encoding='UTF-8') as private:
        private_key = private.read()

    payload = {
            'aud': 'https://iam.' + API_MAIN_DOMAIN + 'iam/v1/tokens',
            'iss': SERVICE_ACCOUNT_ID,
            'iat': int(time.time()),
            'exp': int(time.time()) + 360}

    encoded_token = jwt.encode(
        payload,
        private_key,
        algorithm='PS256',
        headers={'kid': KEY_ID})

    response = requests.post(
        'https://iam.' + API_MAIN_DOMAIN + 'iam/v1/tokens',
        params={"jwt": encoded_token},
        headers={"Content-Type": "application/json"},
        timeout=10
        )

    return response.json()['iamToken']

def make_http_get_request(url: str, payload: dict, bearer_token: str):
    return requests.get(
            url,
            params=payload,
            headers={'Authorization': 'Bearer ' + bearer_token},
            timeout=10
            )

def get_folder_id_by_folder_name(folder_name: str, bearer_token: str) -> Optional[str]:

    payload = {'cloud_id': CLOUD_ID}
    response = make_http_get_request(
        f"https://resource-manager.{API_MAIN_DOMAIN}resource-manager/v1/folders",
        payload,
        bearer_token
        )

    if response.status_code != 200:
        logger.error("Requesting a folder ID by its name returned %s, %s, %s",
                    response.status_code, response.text, response.json)

    for folders in response.json()['folders']:
        if folder_name == folders['name']:
            return folders['id']
    return None

def create_runners_metrics(folder_id: Optional[str], folder_name: str, bearer_token: str):
    if not folder_id:
        return

    payload = {'folder_id': folder_id}
    response = make_http_get_request(
        f"https://compute.{API_MAIN_DOMAIN}compute/v1/instances",
        payload,
        bearer_token
        )

    if response.status_code != 200:
        logger.error("Request a list of instances in a folder %s (%s) returned %s, %s, %s",
                        folder_name, folder_id, response.status_code, response.text, response.json)

    instances = response.json().get('instances', None)

    # If response is not empty
    if instances:
        number_instances = 0
        for instance in instances:
            # if the instance name includes a substring
            # SUBSTRING_IN_VM_NAME and not in BLACKLIST_VM_NAMES
            # print information about it
            if (SUBSTRING_IN_VM_NAME in instance['name']) \
                and (instance['name'] not in BLACKLIST_VM_NAMES):
                number_instances+=1
        metric_runner_up.labels(folder_name, folder_id).set(number_instances)
    else:
        number_instances = 0
        metric_runner_up.labels(folder_name, folder_id).set(number_instances)

def get_folders_dict(bearer_token) -> dict:
    """Get a dictionary with keys from folder names and values from their IDs"""

    folders_dict = {}
    payload = {'cloud_id': CLOUD_ID}
    response = make_http_get_request(
        f"https://resource-manager.{API_MAIN_DOMAIN}resource-manager/v1/folders",
        payload,
        bearer_token
        )

    for folders in response.json()['folders']:
        folders_dict.update({folders['name']:get_folder_id_by_folder_name(folders['name'],
                            bearer_token)})

    return folders_dict


def main():
    """main function"""
    start_http_server(PORT)

    old_time = 0
    folders_dict = {}

    while True:
        # Request an IAM token from Yandex.Cloud no more than once in TOKEN_TTL
        if (time.time() - old_time) > TOKEN_TTL:
            logger.info("Requesting an IAM token")
            try:
                bearer_token = get_iam_token().rstrip("\n")
            except RuntimeError as error:
                logger.error("Error getting IAM token")
                logger.error(error)
                time.sleep(SCRAPE_TIMEOUT)
                continue
            logger.info("Recieved an IAM token %s", bearer_token[-10:])
            old_time = time.time()

        # If the dictionary with folders is empty, then fill it
        # This usually happens on the first iteration
        if not folders_dict:
            try:
                folders_dict = get_folders_dict(bearer_token)
                logger.info("Filled out the dictionary of folders: %s", folders_dict)
                logger.info("Total folders: %i", len(folders_dict))
            except RuntimeError as error:
                logger.error("Folder dictionary filling error %s", folders_dict)
                logger.error(error)
                continue
        try:
            for folder_name in folders_dict:
                create_runners_metrics(folders_dict.get(folder_name), folder_name, bearer_token)
        except RuntimeError as error:
            logger.error(error)
            continue

        time.sleep(SCRAPE_TIMEOUT)

if __name__ == '__main__':
    main()
