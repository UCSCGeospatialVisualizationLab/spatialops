#!/usr/bin/env python3

import json
import os
import random
import subprocess
import sys
import time

REMOTE_PREFIX = (
    "/opt/conda/envs/geospatial-analysis-environment/lib/python3.12/site-packages"
)


def exponential_backoff(f, retries=5, base_delay=1, max_delay=32):
    for i in range(retries):
        delay = min(base_delay * (2**i) + random.uniform(0, 0.1), max_delay)
        time.sleep(delay)
        v = f()
        if v:
            return v
        print(f"Attempt {i + 2}: Waiting {delay:.2f} seconds...")
    raise Exception(f"Failing after {retries} retries")


def get_dev_pod_name():
    username = os.getenv("USER")
    if not username:
        print("Error: USER environment variable not set")
        return None

    result = subprocess.run(
        f"kubectl get pods -l app.kubernetes.io/instance=dev-{username} "
        f"--field-selector=status.phase=Running -o jsonpath={{.items}}".split(" "),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        print("Error: No pod found matching label criteria")
        print(f"kubectl error: {result.stderr}")
        return

    parsed = json.loads(result.stdout)
    # You would think that `phase=Running` would not return pods that are in the
    # `Terminating` phase. You would be wrong!
    non_terminating = [
        pod
        for pod in parsed
        if "deletionTimestamp" not in pod["metadata"]
        or pod["metadata"]["deletionTimestamp"] is None
    ]
    if len(non_terminating) == 1:
        return non_terminating[0]["metadata"]["name"]


def sync_file(package_name, file_path):
    print(f"\n🔄 Detected change in {package_name}. Syncing...")
    local_dir = os.path.abspath(f"{package_name}")
    remote_dir = f"{REMOTE_PREFIX}/{package_name}"
    if file_path == "":
        # In this case we are copying the whole directory and k8s is very
        # particular about how we pass these paths.
        remote_dir = REMOTE_PREFIX
        file_path = local_dir
    else:
        os.path.abspath(file_path)
    if not file_path.startswith(local_dir):
        print(f"Ignoring file change outside of package directory: {file_path}.")
    relative_path = (
        file_path[len(local_dir) + 1 :]
        if file_path.startswith(local_dir)
        else file_path
    )

    pod_name = exponential_backoff(get_dev_pod_name)

    cmd = ["kubectl", "cp", file_path, f"{pod_name}:{remote_dir}/{relative_path}"]
    subprocess.run(cmd, check=False)
    print(f"✅ Synced local {package_name} to remote pod {pod_name}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        sync_file(sys.argv[1], sys.argv[2])
    else:
        print("Error: No file path provided")
        sys.exit(1)
