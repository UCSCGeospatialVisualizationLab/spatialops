import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Literal, Union

import dask
import joblib
from dask.distributed import Client, progress
from typeguard import typechecked

from spatialoperations.logging import silence_logging


@dataclass
class ComputeItem:
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


ComputeItemList = List[ComputeItem]
ComputeMode = Union[Literal["sequential"], Literal["joblib"], Literal["dask"]]


def get_compute(mode: ComputeMode, **kwargs):
    if mode == "sequential":
        return SequentialCompute(**kwargs)
    elif mode == "joblib":
        return JoblibCompute(**kwargs)
    elif mode == "dask":
        return DaskCompute(**kwargs)
    else:
        raise ValueError(f"Invalid execution mode: {mode}")


def silence_logging_wrapper(func: Callable):
    def wrapper(*args, **kwargs):
        silence_logging()
        return func(*args, **kwargs)

    return wrapper


class SequentialCompute:
    def __init__(self, show_progress: bool = False):
        self.show_progress = show_progress

    @typechecked
    def execute(self, func: Callable, items: ComputeItemList):
        buff = []
        if self.show_progress:
            from tqdm import tqdm

            for item in tqdm(items):
                buff.append(func(*item.args, **item.kwargs))
        else:
            for item in items:
                buff.append(func(*item.args, **item.kwargs))
        return buff


class JoblibCompute:
    def __init__(
        self, n_jobs: int = -1, show_progress: bool = False, backend: str = "loky"
    ):
        self.n_jobs = n_jobs
        self.show_progress = show_progress
        self.logger = silence_logging(logging.getLogger("spatialoperations.logger"))
        self.backend = backend

    @typechecked
    def execute(self, func: Callable, items: ComputeItemList):
        func = silence_logging_wrapper(func)
        try:
            if self.show_progress:
                from tqdm import tqdm

                return joblib.Parallel(n_jobs=self.n_jobs, backend=self.backend)(
                    joblib.delayed(func)(*item.args, **item.kwargs)
                    for item in tqdm(items, desc=f"Executing {func.__name__}")
                )
            else:
                return joblib.Parallel(n_jobs=self.n_jobs, backend=self.backend)(
                    joblib.delayed(func)(*item.args, **item.kwargs) for item in items
                )
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up any AWS resources."""
        pass
        # try:
        #     import boto3

        #     # Close any active sessions
        #     boto3.Session()._session.close()
        #     # Reset logging levels
        #     self._setup_logging()
        # except Exception as e:
        #     logging.warning(f"Error during cleanup: {e}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()


class DaskCompute:
    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, client: Client):
        self._client = client

    def __init__(
        self,
        client: Client | None = None,
        show_progress: bool = True,
        dask_logging: bool = False,
    ):
        if client is None:
            self.client = Client()
        else:
            self.client = client
        self.show_progress = show_progress
        self.dask_logging = dask_logging

    @typechecked
    def execute(self, func: Callable, items: ComputeItemList, compute_now: bool = True):
        def set_logs(log_level=logging.WARNING):
            logging.getLogger("Client").setLevel(log_level)
            logging.getLogger("distributed").setLevel(log_level)
            logging.getLogger("dask").setLevel(log_level)
            logging.getLogger("distributed.scheduler").setLevel(log_level)

        if not self.dask_logging:
            set_logs()
        else:
            set_logs(logging.INFO)

        try:
            delayed_func = dask.delayed(func)
            delayed_items = [delayed_func(*item.args, **item.kwargs) for item in items]

            if not compute_now:
                return delayed_items

            futures = self.client.compute(delayed_items)

            if self.show_progress:
                progress(futures, notebook=False)

            # Get results and handle None values
            results = self.client.gather(futures)
            if results is None:
                print("Computation returned None")
                return []

            return [r for r in results if r is not None]
        except Exception as e:
            raise e

    def cleanup(self):
        """Clean up the Dask client and its resources."""
        if hasattr(self, "_client") and self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                logging.warning(f"Error closing Dask client: {e}")
            self._client = None

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()


ComputeType = Union[SequentialCompute, JoblibCompute, DaskCompute]
