import functools
import warnings
from enum import Enum
from typing import Callable, List, Union

import numpy as np
import xarray as xr
from typeguard import typechecked

from spatialoperations.types.xrtypes import RasterLike

CompilerType = Callable[[np.ndarray], np.ndarray]


@typechecked
def compile(
    array: Union[List[RasterLike], np.ndarray],
    metric: str,
    axis: int = 0,
) -> Union[np.ndarray, RasterLike]:
    """
    Compiles a list of RasterLike objects or a NumPy array using a specified metric.

    Args:
        array: The input data, either a list of RasterLike objects or a NumPy array.
        metric: The metric to apply. Supported values: "max", "min", "mean", "median".
        axis: The axis along which to compute the metric (for NumPy arrays).

    Returns:
        A new RasterLike object or a NumPy array with the compiled result.

    Raises:
        ValueError: If an unsupported metric is provided or if the input list of
                    RasterLike objects is empty.
        TypeError: If the input array is not a list of RasterLike or a NumPy array.
    """
    is_raster_like_list = isinstance(array, list) and all(
        isinstance(i, RasterLike) for i in array
    )

    if is_raster_like_list:
        if not array:  # Ensure the list is not empty
            raise ValueError("Input list of RasterLike objects cannot be empty.")

        sample = array[0]
        data_arrays = [i.data for i in array]  # Assumes i.data is xr.DataArray
        stacked_da = xr.concat(data_arrays, dim="stack_dim")

        result_da: xr.DataArray
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=RuntimeWarning, message="Mean of empty slice"
            )
            warnings.filterwarnings(
                "ignore", category=RuntimeWarning, message="All-NaN slice encountered"
            )
            if metric == "max":
                result_da = stacked_da.max(dim="stack_dim", skipna=True)
            elif metric == "min":
                result_da = stacked_da.min(dim="stack_dim", skipna=True)
            elif metric == "mean":
                result_da = stacked_da.mean(dim="stack_dim", skipna=True)
            elif metric == "median":
                result_da = stacked_da.median(dim="stack_dim", skipna=True)
            else:
                raise ValueError(
                    f"Unsupported metric: {metric}. Choose from 'max', 'min', 'mean', 'median'."
                )

        return RasterLike(da=result_da, name=sample.name)

    elif isinstance(array, np.ndarray):
        result_array: np.ndarray
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=RuntimeWarning, message="Mean of empty slice"
            )
            warnings.filterwarnings(
                "ignore", category=RuntimeWarning, message="All-NaN slice encountered"
            )
            if metric == "max":
                result_array = np.nanmax(array, axis=axis)
            elif metric == "min":
                result_array = np.nanmin(array, axis=axis)
            elif metric == "mean":
                result_array = np.nanmean(array, axis=axis)
            elif metric == "median":
                result_array = np.nanmedian(array, axis=axis)
            else:
                raise ValueError(
                    f"Unsupported metric: {metric}. Choose from 'max', 'min', 'mean', 'median'."
                )
        return result_array
    else:
        raise TypeError(
            "Input must be a list of RasterLike objects or a numpy.ndarray."
        )


class Compilers(Enum):
    compile_max: CompilerType = functools.partial(compile, metric="max")
    compile_min: CompilerType = functools.partial(compile, metric="min")
    compile_mean: CompilerType = functools.partial(compile, metric="mean")
    compile_median: CompilerType = functools.partial(compile, metric="median")
