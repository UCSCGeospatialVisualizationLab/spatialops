import io
import logging
import os
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlparse

import s3fs
from typeguard import typechecked

logger = logging.getLogger("spatialoperations._logger")


@typechecked
def run_subprocess_with_output(cmd: str | list[str]) -> tuple[str, str]:
    """Run a subprocess and capture its output using threads.

    Args:
        cmd: Command to run as a list of strings

    Returns:
        Tuple of (stdout_text, stderr_text)

    Raises:
        subprocess.CalledProcessError: If the process returns a non-zero exit code

    """
    if isinstance(cmd, str):
        cmd = cmd.split(" ")

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    def handle_output(stream, buffer, is_stderr=False):
        for line in iter(stream.readline, ""):
            if not line:
                break
            # Print to appropriate stream
            if is_stderr:
                print(line, end="", file=sys.stderr, flush=True)
            else:
                print(line, end="", flush=True)
            # Store in buffer
            buffer.write(line)

    logger.info(f"Running command: {' '.join(cmd)}")
    # Start the process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Create threads to handle stdout and stderr simultaneously
    stdout_thread = threading.Thread(
        target=handle_output, args=(process.stdout, stdout_buffer)
    )
    stderr_thread = threading.Thread(
        target=handle_output, args=(process.stderr, stderr_buffer, True)
    )

    # Start threads
    stdout_thread.start()
    stderr_thread.start()

    try:
        # Wait for process to complete
        return_code = process.wait()

        if return_code != 0:
            # Wait for output threads to complete
            stdout_thread.join()
            stderr_thread.join()

            # Get the complete output
            stdout_text = stdout_buffer.getvalue()
            stderr_text = stderr_buffer.getvalue()
            logger.info(stdout_text)
            logger.error(stderr_text)
            raise subprocess.CalledProcessError(
                return_code, cmd, stdout_text, stderr_text
            )
    except Exception:
        # Ensure process is terminated if an exception occurs
        process.terminate()
        raise
    finally:
        # Always wait for threads to complete, regardless of success or failure
        stdout_thread.join()
        stderr_thread.join()

    return stdout_buffer.getvalue(), stderr_buffer.getvalue()


@typechecked
def move_file_to_destination(local_path: str, destination_path: str) -> None:
    """Move file to either S3 or local storage, with fallback handling for S3 failures.

    Args:
        local_path: Path to the local file to move
        destination_path: Destination path (can be local or s3:// URL)

    Raises:
        Exception: If S3 upload fails (with fallback information)

    """
    if destination_path.startswith("s3://"):
        logger.info(f"Uploading output to S3: {destination_path}")
        try:
            upload_to_s3(local_path, destination_path)
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            # Fallback to local path if S3 upload fails
            local_fallback = f"./output_{os.path.basename(destination_path)}"
            logger.info(f"Saving to local fallback path: {local_fallback}")
            shutil.copy(local_path, local_fallback)
            raise Exception(
                f"S3 upload failed. File saved locally to {local_fallback}"
            ) from e
    else:
        output_dir = os.path.dirname(destination_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Moving output to: {destination_path}")
        shutil.move(local_path, destination_path)


@typechecked
def upload_to_s3(local_path: str, s3_path: str, options: dict | None = None) -> None:
    """Upload a file to S3 using s3fs for all file types.

    Args:
        local_path: Path to the local file to upload
        s3_path: S3 destination path (e.g., 's3://bucket/path/to/file')
        options: Optional dictionary of options:
            - 'content_type': Content type for the file
                 (e.g., 'application/octet-stream')
            - 'metadata': Dict of metadata to attach to the file
            - 'acl': Access control for the file (e.g., 'public-read')
            - Any other options supported by s3fs.put_file

    Example:
        upload_to_s3('local/file.pmtiles', 's3://bucket/path/file.pmtiles')
        upload_to_s3('local/data.parquet', 's3://bucket/data/data.parquet',
                    {'content_type': 'application/parquet'})

    """
    # Check if file exists
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    # Parse S3 path
    parsed_url = urlparse(s3_path)
    bucket_name = parsed_url.netloc
    key = parsed_url.path.lstrip("/")

    # If key ends with '/', append the filename from local_path
    if key.endswith("/"):
        key = key + os.path.basename(local_path)

    # Full S3 path without the s3:// prefix
    s3_full_path = f"{bucket_name}/{key}"

    # Set default content type based on file extension
    content_type = None
    if local_path.lower().endswith(".pmtiles"):
        content_type = "application/octet-stream"
    elif local_path.lower().endswith(".parquet"):
        content_type = "application/parquet"
    elif local_path.lower().endswith(".geojson"):
        content_type = "application/geo+json"

    # Create s3fs filesystem
    # This will use AWS credentials from environment variables
    fs = s3fs.S3FileSystem()

    # Get file size for progress reporting
    file_size = os.path.getsize(local_path)

    # Prepare extra arguments for the upload
    extra_args = {}
    if options:
        # Extract content_type from options if provided
        if "content_type" in options:
            content_type = options.pop("content_type")

        # Add remaining options to extra_args
        extra_args.update(options)

    # Add content_type to extra_args if set
    if content_type:
        extra_args["ContentType"] = content_type

    logger.info(
        f"Uploading {local_path} to {s3_path} ({file_size / (1024 * 1024):.2f} MB)"
    )

    try:
        # Upload with progress tracking
        uploaded = 0
        chunk_size = 5 * 1024 * 1024  # 5MB chunks

        with open(local_path, "rb") as local_file:
            with fs.open(s3_full_path, "wb", **extra_args) as s3_file:
                while True:
                    chunk = local_file.read(chunk_size)
                    if not chunk:
                        break
                    s3_file.write(chunk)
                    uploaded += len(chunk)
                    percent = (uploaded / file_size) * 100
                    logger.info(
                        f"Progress: {percent:.1f}% "
                        f"({uploaded / (1024 * 1024):.2f} MB / "
                        f"{file_size / (1024 * 1024):.2f} MB)"
                    )

        logger.info(f"Successfully uploaded {local_path} to {s3_path}")

    except Exception as e:
        raise Exception(f"Failed to upload file: {str(e)}") from e
