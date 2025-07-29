import logging

from typeguard import typechecked

logger = logging.getLogger("spatialoperations.logger")
logger.setLevel(logging.WARNING)

loggers_I_dont_like = [
    "boto3",
    "botocore",
    "botocore.credentials",
    "fsspec",
    "s3fs",
    "aiobotocore",
    "s3transfer",
    "urllib3",
]


@typechecked
def silence_logging(logger: logging.Logger = logger):
    # Optionally, silence unwanted loggers by setting their level high
    for logger_name in loggers_I_dont_like:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    return logger


silence_logging(logger)
