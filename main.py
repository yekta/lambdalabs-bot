import os
import requests
import time
import logging
from threading import Thread
from flask import Flask, jsonify
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

# Configuration from environment variables
API_KEY = os.getenv("LAMBDA_API_KEY")
INSTANCE_TYPE_NAME = os.getenv("INSTANCE_TYPE_NAME", "gpu_1x_a6000")
SSH_KEY_NAME = os.getenv("SSH_KEY_NAME")
CHECK_INTERVAL_SECONDS = int(
    os.getenv("CHECK_INTERVAL_SECONDS", 30)
)  # Interval to check availability
ERROR_WAIT_SECONDS = int(
    os.getenv("ERROR_WAIT_SECONDS", 10)
)  # Wait time after an error

BASE_URL = "https://cloud.lambdalabs.com/api/v1/"
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

# Health status
health_status = {"status": "starting"}

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_instance_types():
    url = BASE_URL + "instance-types"
    logger.info("Fetching instance types...")
    response = requests.get(url, auth=HTTPBasicAuth(API_KEY, ""))
    response.raise_for_status()
    logger.info("Instance types fetched successfully.")
    return response.json()


def check_instance_availability(instance_types, instance_type_name):
    logger.info(f"Checking availability for instance type: {instance_type_name}...")
    if instance_type_name in instance_types["data"]:
        regions = instance_types["data"][instance_type_name][
            "regions_with_capacity_available"
        ]
        if regions:
            region_name = regions[0]["name"]
            logger.info(
                f"Instance type {instance_type_name} is available in region: {region_name}."
            )
            return region_name
    logger.info(f"Instance type {instance_type_name} is not available in any region.")
    return None


def launch_instance(region_name, instance_type_name, ssh_key_name):
    url = BASE_URL + "instance-operations/launch"
    payload = {
        "region_name": region_name,
        "instance_type_name": instance_type_name,
        "ssh_key_names": [ssh_key_name],
        "quantity": 1,
    }
    logger.info(
        f"Launching instance {instance_type_name} in region {region_name} with SSH key {ssh_key_name}..."
    )
    response = requests.post(url, json=payload, auth=HTTPBasicAuth(API_KEY, ""))
    response.raise_for_status()
    logger.info("Instance launched successfully.")
    return response.json()


def launch_instance_loop():
    global health_status
    while True:
        logger.info(
            "\n" + "=" * 40 + "\n"
        )  # Add a line break and separator before each batch of logs
        try:
            instance_types = get_instance_types()
            region_name = check_instance_availability(
                instance_types, INSTANCE_TYPE_NAME
            )

            if region_name:
                result = launch_instance(region_name, INSTANCE_TYPE_NAME, SSH_KEY_NAME)
                logger.info("Instance launch result: %s", result)
                health_status = {"status": "instance launched", "result": result}
                break
            else:
                logger.info(
                    f"No available regions found for instance type {INSTANCE_TYPE_NAME}. Checking again in {CHECK_INTERVAL_SECONDS} seconds."
                )

        except requests.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred: {http_err}. Retrying in {ERROR_WAIT_SECONDS} seconds."
            )
            health_status = {"status": "error", "error": str(http_err)}
            time.sleep(ERROR_WAIT_SECONDS)
        except Exception as err:
            logger.error(
                f"An error occurred: {err}. Retrying in {ERROR_WAIT_SECONDS} seconds."
            )
            health_status = {"status": "error", "error": str(err)}
            time.sleep(ERROR_WAIT_SECONDS)

        time.sleep(CHECK_INTERVAL_SECONDS)


@app.route("/health", methods=["GET"])
def health():
    return jsonify(health_status)


if __name__ == "__main__":
    logger.info("Starting instance launcher script...")
    health_status = {"status": "running"}
    Thread(target=launch_instance_loop).start()
    app.run(host="0.0.0.0", port=PORT)
    logger.info("Instance launcher script finished.")
