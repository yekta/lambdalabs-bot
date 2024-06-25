import os
import requests
import time
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


def get_instance_types():
    url = BASE_URL + "instance-types"
    print("Fetching instance types...")
    response = requests.get(url, auth=HTTPBasicAuth(API_KEY, ""))
    response.raise_for_status()
    print("Instance types fetched successfully.")
    return response.json()


def check_instance_availability(instance_types, instance_type_name):
    print(f"Checking availability for instance type: {instance_type_name}...")
    if instance_type_name in instance_types["data"]:
        regions = instance_types["data"][instance_type_name][
            "regions_with_capacity_available"
        ]
        if regions:
            region_name = regions[0]["name"]
            print(
                f"Instance type {instance_type_name} is available in region: {region_name}."
            )
            return region_name
    print(f"Instance type {instance_type_name} is not available in any region.")
    return None


def launch_instance(region_name, instance_type_name, ssh_key_name):
    url = BASE_URL + "instance-operations/launch"
    payload = {
        "region_name": region_name,
        "instance_type_name": instance_type_name,
        "ssh_key_names": [ssh_key_name],
        "quantity": 1,
    }
    print(
        f"Launching instance {instance_type_name} in region {region_name} with SSH key {ssh_key_name}..."
    )
    response = requests.post(url, json=payload, auth=HTTPBasicAuth(API_KEY, ""))
    response.raise_for_status()
    print("Instance launched successfully.")
    return response.json()


def main():
    while True:
        print(
            "\n" + "=" * 40 + "\n"
        )  # Add a line break and separator before each batch of logs
        try:
            instance_types = get_instance_types()
            region_name = check_instance_availability(
                instance_types, INSTANCE_TYPE_NAME
            )

            if region_name:
                result = launch_instance(region_name, INSTANCE_TYPE_NAME, SSH_KEY_NAME)
                print("Instance launch result:", result)
                break
            else:
                print(
                    f"No available regions found for instance type {INSTANCE_TYPE_NAME}. Checking again in {CHECK_INTERVAL_SECONDS} seconds."
                )

        except requests.HTTPError as http_err:
            print(
                f"HTTP error occurred: {http_err}. Retrying in {ERROR_WAIT_SECONDS} seconds."
            )
            time.sleep(ERROR_WAIT_SECONDS)
        except Exception as err:
            print(
                f"An error occurred: {err}. Retrying in {ERROR_WAIT_SECONDS} seconds."
            )
            time.sleep(ERROR_WAIT_SECONDS)

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    print("Starting instance launcher script...")
    main()
    print("Instance launcher script finished.")
