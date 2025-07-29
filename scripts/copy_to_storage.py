#!/usr/bin/env python3

import argparse
import os
import random
import shutil
import subprocess
import sys
import time


def get_dev_deployment_name():
    """Get the development deployment name using the same convention
    as in dev script.
    """

    username = os.environ.get("USER")
    if not username:
        print("Warning: USER environment variable not set, using 'default'")
        username = "default"
    return f"dev-{username}"


def exponential_backoff(f, retries=5, base_delay=1, max_delay=32):
    """Retry a function with exponential backoff."""
    for i in range(retries):
        try:
            return f()
        except Exception as e:
            if i == retries - 1:
                raise e
            delay = min(base_delay * (2**i) + random.uniform(0, 0.1), max_delay)
            print(f"Attempt {i + 1} failed: {e}. Retrying in {delay:.2f} seconds...")
            time.sleep(delay)


def is_command_available(command):
    """Check if a command is available in the system."""
    return shutil.which(command) is not None


def list_available_jupyter_pods():
    """List all available jupyter pods in the current namespace."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "pods",
            "-l",
            "app.kubernetes.io/name=jupyter",
            "--show-labels",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0 and result.stdout:
        print("\nAvailable Jupyter pods:")
        print(result.stdout)

        # Try to extract the deployment names from the labels
        import re

        pattern = r"app.kubernetes.io/instance=([^\s,]+)"
        matches = re.findall(pattern, result.stdout)

        if matches:
            print("\nPossible deployment names to use:")
            for match in matches:
                print(f"  {match}")
            print("\nTry running your command with DEPLOYMENT=<name> parameter")
            print("Or with DEV=true for development deployment")
    else:
        print("\nNo Jupyter pods found in the current namespace.")
        print("Make sure you have deployed the Jupyter server with:")
        print("  make jupyter-deploy")
        print("Or for development:")
        print("  make jupyter-deploy-dev")


def get_jupyter_pod_name(deployment_name):
    """Get the name of the running Jupyter pod."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "pods",
            "-l",
            f"app.kubernetes.io/instance={deployment_name}",
            "--field-selector=status.phase=Running",
            "-o",
            "jsonpath={.items[*].metadata.name}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0 or not result.stdout:
        print(f"Error: No pod found for deployment '{deployment_name}'")
        print(f"kubectl error: {result.stderr}")
        list_available_jupyter_pods()
        return None

    # Split in case there are multiple pods
    pods = result.stdout.strip().split()
    if not pods:
        print(f"Error: No running pods found for deployment '{deployment_name}'")
        list_available_jupyter_pods()
        return None

    return pods[0]  # Return the first pod


def copy_to_storage(local_path, remote_path=None, deployment_name=None):
    """Copy a file or directory to the persistent storage in the pod using tar
    for efficiency.
    """

    if deployment_name is None:
        deployment_name = os.environ.get("USER")

    # Ensure the local path exists
    if not os.path.exists(local_path):
        print(f"Error: Local path '{local_path}' does not exist")
        return False

    # Get the pod name
    pod_name = exponential_backoff(lambda: get_jupyter_pod_name(deployment_name))
    if not pod_name:
        return False

    # If no remote path specified, use the basename of the local path
    if not remote_path:
        remote_path = os.path.basename(os.path.normpath(local_path))

    # The persistent volume is mounted at /app/persistent-storage
    remote_dest_dir = f"/app/persistent-storage/{os.path.dirname(remote_path)}"

    # Create the destination directory structure if it doesn't exist
    subprocess.run(
        ["kubectl", "exec", pod_name, "--", "mkdir", "-p", remote_dest_dir], check=False
    )

    remote_full_path = f"/app/persistent-storage/{remote_path}"

    print(f"Copying {local_path} to {pod_name}:{remote_full_path}")

    # Get absolute paths to avoid directory traversal issues
    local_path_abs = os.path.abspath(local_path)

    try:
        # Check if pv is available for progress visualization
        has_pv = is_command_available("pv")
        if has_pv:
            # With pv for progress visualization
            proc1 = subprocess.Popen(
                [
                    "tar",
                    "cf",
                    "-",
                    "-C",
                    os.path.dirname(local_path_abs),
                    os.path.basename(local_path_abs),
                ],
                stdout=subprocess.PIPE,
            )
            proc2 = subprocess.Popen(["pv"], stdin=proc1.stdout, stdout=subprocess.PIPE)
            proc3 = subprocess.Popen(
                [
                    "kubectl",
                    "exec",
                    "-i",
                    pod_name,
                    "--",
                    "tar",
                    "xf",
                    "-",
                    "-C",
                    remote_dest_dir,
                ],
                stdin=proc2.stdout,
            )
            proc1.stdout.close()  # Allow proc1 to receive SIGPIPE if proc2 exits
            proc2.stdout.close()  # Allow proc2 to receive SIGPIPE if proc3 exits
            proc3.wait()
            result = proc3.returncode
        else:
            print("(install pv for progress visualization)")
            # Without pv, direct pipe
            proc1 = subprocess.Popen(
                [
                    "tar",
                    "cf",
                    "-",
                    "-C",
                    os.path.dirname(local_path_abs),
                    os.path.basename(local_path_abs),
                ],
                stdout=subprocess.PIPE,
            )
            proc2 = subprocess.Popen(
                [
                    "kubectl",
                    "exec",
                    "-i",
                    pod_name,
                    "--",
                    "tar",
                    "xf",
                    "-",
                    "-C",
                    remote_dest_dir,
                ],
                stdin=proc1.stdout,
            )
            proc1.stdout.close()  # Allow proc1 to receive SIGPIPE if proc2 exits
            proc2.wait()
            result = proc2.returncode

        if result == 0:
            print("Successfully copied to persistent storage")
            return True
        else:
            print(f"Error copying to persistent storage (tar exit code: {result})")
            print("Falling back to kubectl cp method...")
            # Fall back to kubectl cp
            return copy_with_kubectl(local_path, remote_full_path, pod_name)

    except Exception as e:
        print(f"Error during tar transfer: {str(e)}")
        print("Falling back to kubectl cp method...")
        return copy_with_kubectl(local_path, remote_full_path, pod_name)


def copy_with_kubectl(local_path, remote_full_path, pod_name):
    """Fall back to kubectl cp for file transfer."""
    print("Using kubectl cp for file transfer")
    cmd = ["kubectl", "cp", local_path, f"{pod_name}:{remote_full_path}"]
    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        print("Successfully copied to persistent storage using kubectl cp")
        return True
    else:
        print(
            f"Error copying to persistent storage with kubectl cp "
            f"(exit code: {result.returncode})"
        )
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Copy files to Jupyter persistent storage"
    )
    parser.add_argument("local_path", help="Local file or directory to copy")
    parser.add_argument(
        "--remote-path",
        help=(
            "Remote path relative to persistent storage root "
            "(default: basename of local path)"
        ),
    )
    parser.add_argument(
        "--deployment",
        help="Name of the Jupyter deployment (default: jupyter)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use development deployment (jupyter-dev-$USER)",
    )

    args = parser.parse_args()

    # Determine deployment name
    if args.dev:
        deployment_name = get_dev_deployment_name()
        print(f"Using development deployment: {deployment_name}")
    else:
        deployment_name = args.deployment or os.environ.get("USER")

    success = copy_to_storage(args.local_path, args.remote_path, deployment_name)

    sys.exit(0 if success else 1)
