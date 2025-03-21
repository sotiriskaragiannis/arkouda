from enum import Enum
from typing import ForwardRef, Optional, Tuple, Union
from typing import cast as type_cast

import numpy as np  # type: ignore
from typeguard import typechecked

from arkouda.client import generic_msg
from arkouda.dtypes import (
    DTypes,
    _as_dtype,
    int_scalars,
    isSupportedNumber,
    numeric_scalars,
    resolve_scalar_dtype,
)
from arkouda.groupbyclass import GroupBy
from arkouda.pdarrayclass import create_pdarray, pdarray
from arkouda.strings import Strings

Categorical = ForwardRef("Categorical")

__all__ = [
    "cast",
    "abs",
    "log",
    "exp",
    "cumsum",
    "cumprod",
    "sin",
    "cos",
    "hash",
    "where",
    "histogram",
    "value_counts",
    "isnan",
    "ErrorMode",
]


class ErrorMode(Enum):
    strict = "strict"
    ignore = "ignore"
    return_validity = "return_validity"


@typechecked
def cast(
    pda: Union[pdarray, Strings], dt: Union[np.dtype, type, str], errors: ErrorMode = ErrorMode.strict
) -> Union[Union[pdarray, Strings], Tuple[pdarray, pdarray]]:
    """
    Cast an array to another dtype.

    Parameters
    ----------
    pda : pdarray or Strings
        The array of values to cast
    dt : np.dtype, type, or str
        The target dtype to cast values to
    errors : {strict, ignore, return_validity}
        Controls how errors are handled when casting strings to a numeric type
        (ignored for casts from numeric types).
            - strict: raise RuntimeError if *any* string cannot be converted
            - ignore: never raise an error. Uninterpretable strings get
                converted to NaN (float64), -2**63 (int64), zero (uint64 and
                uint8), or False (bool)
            - return_validity: in addition to returning the same output as
              "ignore", also return a bool array indicating where the cast
              was successful.

    Returns
    -------
    pdarray or Strings
        Array of values cast to desired dtype
    [validity : pdarray(bool)]
        If errors="return_validity" and input is Strings, a second array is
        returned with True where the cast succeeded and False where it failed.

    Notes
    -----
    The cast is performed according to Chapel's casting rules and is NOT safe
    from overflows or underflows. The user must ensure that the target dtype
    has the precision and capacity to hold the desired result.

    Examples
    --------
    >>> ak.cast(ak.linspace(1.0,5.0,5), dt=ak.int64)
    array([1, 2, 3, 4, 5])

    >>> ak.cast(ak.arange(0,5), dt=ak.float64).dtype
    dtype('float64')

    >>> ak.cast(ak.arange(0,5), dt=ak.bool)
    array([False, True, True, True, True])

    >>> ak.cast(ak.linspace(0,4,5), dt=ak.bool)
    array([False, True, True, True, True])
    """

    if isinstance(pda, pdarray):
        name = pda.name
        objtype = "pdarray"
    elif isinstance(pda, Strings):
        name = pda.entry.name
        objtype = "str"
    # typechecked decorator guarantees no other case

    dt = _as_dtype(dt)
    cmd = "cast"
    repMsg = generic_msg(
        cmd=cmd,
        args={
            "name": name,
            "objType": objtype,
            "targetDtype": dt.name,
            "opt": errors.name,
        },
    )
    if dt.name.startswith("str"):
        return Strings.from_parts(*(type_cast(str, repMsg).split("+")))
    else:
        if errors == ErrorMode.return_validity:
            a, b = type_cast(str, repMsg).split("+")
            return create_pdarray(type_cast(str, a)), create_pdarray(type_cast(str, b))
        else:
            return create_pdarray(type_cast(str, repMsg))


@typechecked
def abs(pda: pdarray) -> pdarray:
    """
    Return the element-wise absolute value of the array.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing absolute values of the input array elements

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    Examples
    --------
    >>> ak.abs(ak.arange(-5,-1))
    array([5, 4, 3, 2])

    >>> ak.abs(ak.linspace(-5,-1,5))
    array([5, 4, 3, 2, 1])
    """
    repMsg = generic_msg(
        cmd="efunc",
        args={
            "func": "abs",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def log(pda: pdarray) -> pdarray:
    """
    Return the element-wise natural log of the array.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing natural log values of the input
        array elements

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    Notes
    -----
    Logarithms with other bases can be computed as follows:

    Examples
    --------
    >>> A = ak.array([1, 10, 100])
    # Natural log
    >>> ak.log(A)
    array([0, 2.3025850929940459, 4.6051701859880918])
    # Log base 10
    >>> ak.log(A) / np.log(10)
    array([0, 1, 2])
    # Log base 2
    >>> ak.log(A) / np.log(2)
    array([0, 3.3219280948873626, 6.6438561897747253])
    """
    repMsg = generic_msg(
        cmd="efunc",
        args={
            "func": "log",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def log10(x: pdarray) -> pdarray:
    """
    compute the log of a pdarray and perform a basechange

    Parameters
    __________
    x : pdarray
        array to compute on

    Returns
    _______
    pdarray contain values of the base 10 log
    """
    basechange = float(np.log10(np.exp(1)))
    return basechange * log(x)


@typechecked
def exp(pda: pdarray) -> pdarray:
    """
    Return the element-wise exponential of the array.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing exponential values of the input
        array elements

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    Examples
    --------
    >>> ak.exp(ak.arange(1,5))
    array([2.7182818284590451, 7.3890560989306504, 20.085536923187668, 54.598150033144236])

    >>> ak.exp(ak.uniform(5,1.0,5.0))
    array([11.84010843172504, 46.454368507659211, 5.5571769623557188,
           33.494295836924771, 13.478894913238722])
    """
    repMsg = generic_msg(
        cmd="efunc",
        args={
            "func": "exp",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def cumsum(pda: pdarray) -> pdarray:
    """
    Return the cumulative sum over the array.

    The sum is inclusive, such that the ``i`` th element of the
    result is the sum of elements up to and including ``i``.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing cumulative sums for each element
        of the original pdarray

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    Examples
    --------
    >>> ak.cumsum(ak.arange([1,5]))
    array([1, 3, 6])

    >>> ak.cumsum(ak.uniform(5,1.0,5.0))
    array([3.1598310770203937, 5.4110385860243131, 9.1622479306453748,
           12.710615785506533, 13.945880905466208])

    >>> ak.cumsum(ak.randint(0, 1, 5, dtype=ak.bool))
    array([0, 1, 1, 2, 3])
    """
    repMsg = generic_msg(
        cmd="efunc",
        args={
            "func": "cumsum",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def cumprod(pda: pdarray) -> pdarray:
    """
    Return the cumulative product over the array.

    The product is inclusive, such that the ``i`` th element of the
    result is the product of elements up to and including ``i``.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing cumulative products for each element
        of the original pdarray

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    Examples
    --------
    >>> ak.cumprod(ak.arange(1,5))
    array([1, 2, 6, 24]))

    >>> ak.cumprod(ak.uniform(5,1.0,5.0))
    array([1.5728783400481925, 7.0472855509390593, 33.78523998586553,
           134.05309592737584, 450.21589865655358])
    """
    repMsg = generic_msg(
        cmd="efunc",
        args={
            "func": "cumprod",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def sin(pda: pdarray) -> pdarray:
    """
    Return the element-wise sine of the array.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing sin for each element
        of the original pdarray

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray
    """
    repMsg = generic_msg(
        cmd="efunc",
        args={
            "func": "sin",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def cos(pda: pdarray) -> pdarray:
    """
    Return the element-wise cosine of the array.

    Parameters
    ----------
    pda : pdarray

    Returns
    -------
    pdarray
        A pdarray containing cosine for each element
        of the original pdarray

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray
    """
    repMsg = type_cast(
        str,
        generic_msg(
            cmd="efunc",
            args={
                "func": "cos",
                "array": pda,
            },
        ),
    )
    return create_pdarray(repMsg)


@typechecked
def hash(pda: pdarray, full: bool = True) -> Union[Tuple[pdarray, pdarray], pdarray]:
    """
    Return an element-wise hash of the array.

    Parameters
    ----------
    pda : pdarray

    full : bool
        By default, a 128-bit hash is computed and returned as
        two int64 arrays. If full=False, then a 64-bit hash
        is computed and returned as a single int64 array.

    Returns
    -------
    hashes
        If full=True, a 2-tuple of pdarrays containing the high
        and low 64 bits of each hash, respectively.
        If full=False, a single pdarray containing a 64-bit hash

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    Notes
    -----
    This function uses the SIPhash algorithm, which can output
    either a 64-bit or 128-bit hash. However, the 64-bit hash
    runs a significant risk of collisions when applied to more
    than a few million unique values. Unless the number of unique
    values is known to be small, the 128-bit hash is strongly
    recommended.

    Note that this hash should not be used for security, or for
    any cryptographic application. Not only is SIPhash not
    intended for such uses, but this implementation employs a
    fixed key for the hash, which makes it possible for an
    adversary with control over input to engineer collisions.
    """
    repMsg = type_cast(
        str,
        generic_msg(
            cmd="efunc",
            args={
                "func": "hash128" if full else "hash64",
                "array": pda,
            },
        ),
    )
    if full:
        a, b = repMsg.split("+")
        return create_pdarray(a), create_pdarray(b)
    else:
        return create_pdarray(repMsg)


@typechecked
def where(
    condition: pdarray, A: Union[numeric_scalars, pdarray], B: Union[numeric_scalars, pdarray]
) -> pdarray:
    """
    Returns an array with elements chosen from A and B based upon a
    conditioning array. As is the case with numpy.where, the return array
    consists of values from the first array (A) where the conditioning array
    elements are True and from the second array (B) where the conditioning
    array elements are False.

    Parameters
    ----------
    condition : pdarray
        Used to choose values from A or B
    A : Union[numeric_scalars, pdarray]
        Value(s) used when condition is True
    B : Union[numeric_scalars, pdarray]
        Value(s) used when condition is False

    Returns
    -------
    pdarray
        Values chosen from A where the condition is True and B where
        the condition is False

    Raises
    ------
    TypeError
        Raised if the condition object is not a pdarray, if A or B is not
        an int, np.int64, float, np.float64, or pdarray, if pdarray dtypes
        are not supported or do not match, or multiple condition clauses (see
        Notes section) are applied
    ValueError
        Raised if the shapes of the condition, A, and B pdarrays are unequal

    Examples
    --------
    >>> a1 = ak.arange(1,10)
    >>> a2 = ak.ones(9, dtype=np.int64)
    >>> cond = a1 < 5
    >>> ak.where(cond,a1,a2)
    array([1, 2, 3, 4, 1, 1, 1, 1, 1])

    >>> a1 = ak.arange(1,10)
    >>> a2 = ak.ones(9, dtype=np.int64)
    >>> cond = a1 == 5
    >>> ak.where(cond,a1,a2)
    array([1, 1, 1, 1, 5, 1, 1, 1, 1])

    >>> a1 = ak.arange(1,10)
    >>> a2 = 10
    >>> cond = a1 < 5
    >>> ak.where(cond,a1,a2)
    array([1, 2, 3, 4, 10, 10, 10, 10, 10])

    Notes
    -----
    A and B must have the same dtype and only one conditional clause
    is supported e.g., n < 5, n > 1, which is supported in numpy
    is not currently supported in Arkouda
    """
    if (not isSupportedNumber(A) and not isinstance(A, pdarray)) or (
        not isSupportedNumber(B) and not isinstance(B, pdarray)
    ):
        raise TypeError("both A and B must be an int, np.int64, float, np.float64, or pdarray")
    if isinstance(A, pdarray) and isinstance(B, pdarray):
        repMsg = generic_msg(
            cmd="efunc3vv",
            args={
                "func": "where",
                "condition": condition,
                "a": A,
                "b": B,
            },
        )
    # For scalars, try to convert it to the array's dtype
    elif isinstance(A, pdarray) and np.isscalar(B):
        repMsg = generic_msg(
            cmd="efunc3vs",
            args={
                "func": "where",
                "condition": condition,
                "a": A,
                "dtype": A.dtype.name,
                "scalar": A.format_other(B),
            },
        )
    elif isinstance(B, pdarray) and np.isscalar(A):
        repMsg = generic_msg(
            cmd="efunc3sv",
            args={
                "func": "where",
                "condition": condition,
                "dtype": B.dtype.name,
                "scalar": B.format_other(A),
                "b": B,
            },
        )
    elif np.isscalar(A) and np.isscalar(B):
        # Scalars must share a common dtype (or be cast)
        dtA = resolve_scalar_dtype(A)
        dtB = resolve_scalar_dtype(B)
        # Make sure at least one of the dtypes is supported
        if not (dtA in DTypes or dtB in DTypes):
            raise TypeError(f"Not implemented for scalar types {dtA} and {dtB}")
        # If the dtypes are the same, do not cast
        if dtA == dtB:  # type: ignore
            dt = dtA
        # If the dtypes are different, try casting one direction then the other
        elif dtB in DTypes and np.can_cast(A, dtB):
            A = np.dtype(dtB).type(A)  # type: ignore
            dt = dtB
        elif dtA in DTypes and np.can_cast(B, dtA):
            B = np.dtype(dtA).type(B)  # type: ignore
            dt = dtA
        # Cannot safely cast
        else:
            raise TypeError(f"Cannot cast between scalars {str(A)} and {str(B)} to supported dtype")
        repMsg = generic_msg(
            cmd="efunc3ss",
            args={
                "func": "where",
                "condition": condition,
                "dtype": dt,
                "a": A,
                "b": B,
            },
        )
    return create_pdarray(type_cast(str, repMsg))


@typechecked
def histogram(pda: pdarray, bins: int_scalars = 10) -> Tuple[np.ndarray, pdarray]:
    """
    Compute a histogram of evenly spaced bins over the range of an array.

    Parameters
    ----------
    pda : pdarray
        The values to histogram

    bins : int_scalars
        The number of equal-size bins to use (default: 10)

    Returns
    -------
    (np.ndarray, Union[pdarray, int64 or float64])
        Bin edges and The number of values present in each bin

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray or if bins is
        not an int.
    ValueError
        Raised if bins < 1
    NotImplementedError
        Raised if pdarray dtype is bool or uint8

    See Also
    --------
    value_counts

    Notes
    -----
    The bins are evenly spaced in the interval [pda.min(), pda.max()].

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> A = ak.arange(0, 10, 1)
    >>> nbins = 3
    >>> b, h = ak.histogram(A, bins=nbins)
    >>> h
    array([3, 3, 4])
    >>> b
    array([0., 3., 6.])

    # To plot, use only the left edges (now returned), and export the histogram to NumPy
    >>> plt.plot(b, h.to_ndarray())
    """
    if bins < 1:
        raise ValueError("bins must be 1 or greater")
    b = np.linspace(pda.min(), pda.max(), bins + 1)[:-1]  # type: ignore
    repMsg = generic_msg(cmd="histogram", args={
        "array": pda,
        "bins": bins
    })
    return b, create_pdarray(type_cast(str, repMsg))


@typechecked
def value_counts(
    pda: pdarray,
) -> Union[Categorical, Tuple[Union[pdarray, Strings], Optional[pdarray]]]:  # type: ignore
    """
    Count the occurrences of the unique values of an array.

    Parameters
    ----------
    pda : pdarray, int64
        The array of values to count

    Returns
    -------
    unique_values : pdarray, int64 or Strings
        The unique values, sorted in ascending order

    counts : pdarray, int64
        The number of times the corresponding unique value occurs

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray

    See Also
    --------
    unique, histogram

    Notes
    -----
    This function differs from ``histogram()`` in that it only returns
    counts for values that are present, leaving out empty "bins". This
    function delegates all logic to the unique() method where the
    return_counts parameter is set to True.

    Examples
    --------
    >>> A = ak.array([2, 0, 2, 4, 0, 0])
    >>> ak.value_counts(A)
    (array([0, 2, 4]), array([3, 2, 1]))
    """
    return GroupBy(pda).count()


@typechecked
def isnan(pda: pdarray) -> pdarray:
    """
    Test a pdarray for Not a number / NaN values
    Currently only supports float-value-based arrays

    Parameters
    ----------
    pda : pdarray to test

    Returns
    -------
    pdarray consisting of True / False values; True where NaN, False otherwise

    Raises
    ------
    TypeError
        Raised if the parameter is not a pdarray
    RuntimeError
        if the underlying pdarray is not float-based
    """
    rep_msg = generic_msg(
        cmd="efunc",
        args={
            "func": "isnan",
            "array": pda,
        },
    )
    return create_pdarray(type_cast(str, rep_msg))
