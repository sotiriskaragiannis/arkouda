import functools
from warnings import warn

import numpy as np  # type: ignore

from arkouda.categorical import Categorical
from arkouda.dtypes import float64 as akfloat64
from arkouda.dtypes import int64 as akint64
from arkouda.dtypes import uint64 as akuint64
from arkouda.groupbyclass import GroupBy, broadcast, unique
from arkouda.numeric import where
from arkouda.pdarrayclass import pdarray
from arkouda.pdarraycreation import arange, full, ones, zeros
from arkouda.pdarraysetops import concatenate, in1d
from arkouda.sorting import argsort
from arkouda.strings import Strings


def unsqueeze(p):
    if isinstance(p, pdarray) or isinstance(p, Strings) or isinstance(p, Categorical):
        return [p]
    else:
        return p


def zero_up(vals):
    """
    Map an array of sparse values to 0-up indices.

    Parameters
    ----------
    vals : pdarray
        Array to map to dense index

    Returns
    -------
    aligned : pdarray
        Array with values replaced by 0-up indices
    """
    g = GroupBy(vals)
    uniqueInds = arange(g.unique_keys.size)
    idinds = g.broadcast(uniqueInds, permute=True)
    return idinds


def align(*args):
    """
    Map multiple arrays of sparse identifiers to a common 0-up index.

    Parameters
    ----------
    *args : pdarrays
        Arrays to map to dense index

    Returns
    -------
    aligned : list of pdarrays
        Arrays with values replaced by 0-up indices
    """
    c = concatenate(args)
    inds = zero_up(c)
    pos = 0
    ret = []
    for arg in args:
        ret.append(inds[pos : pos + arg.size])
        pos += arg.size
    return ret


def right_align(left, right):
    """
    Map two arrays of sparse values to the 0-up index set implied by the right array,
    discarding values from left that do not appear in right.

    Parameters
    ----------
    left : pdarray
        Left-hand identifiers
    right : pdarray
        Right-hand identifiers that define the index

    Returns
    -------
    keep : pdarray, bool
        Logical index of left-hand values that survived
    aligned : (pdarray, pdarray)
        Left and right arrays with values replaced by 0-up indices
    """
    uright = unique(right)
    keep = in1d(left, uright)
    fleft = left[keep]
    return keep, align(fleft, right)


def left_align(left, right):
    """
    Map two arrays of sparse identifiers to the 0-up index set implied by the left array,
    discarding values from right that do not appear in left.
    """
    return right_align(right, left)


class NonUniqueError(ValueError):
    pass


def find(query, space):
    """
    Return indices of query items in a search list of items (-1 if not found).

    Parameters
    ----------
    query : (sequence of) array-like
        The items to search for. If multiple arrays, each "row" is an item.
    space : (sequence of) array-like
        The set of items in which to search. Must have same shape/dtype as query.

    Returns
    -------
    indices : pdarray, int64
        For each item in query, its index in space or -1 if not found.
    """

    # Concatenate the space and query in fast (block interleaved) mode
    if isinstance(query, (pdarray, Strings, Categorical)):
        if type(query) != type(space):
            raise TypeError("Arguments must have same type")
        c = concatenate((space, query), ordered=False)
        spacesize = space.size
        querysize = query.size
    else:
        if len(query) != len(space):
            raise TypeError("Multi-array arguments must have same number of arrays")
        spacesize = set(s.size for s in space)
        querysize = set(q.size for q in query)
        if len(spacesize) != 1 or len(querysize) != 1:
            raise TypeError("Multi-array arguments must be non-empty and have equal-length arrays")
        spacesize = spacesize.pop()
        querysize = querysize.pop()
        atypes = np.array([ai.dtype for ai in query])
        btypes = np.array([bi.dtype for bi in space])
        if not (atypes == btypes).all():
            raise TypeError("Array dtypes of arguments must match")
        c = [concatenate((si, qi), ordered=False) for si, qi in zip(space, query)]
    # Combined index of space and query elements, in block interleaved order
    # All space indices are less than all query indices
    i = concatenate((arange(spacesize), arange(spacesize, spacesize + querysize)), ordered=False)
    # Group on terms
    g = GroupBy(c)
    # For each term, count how many times it appears in the search space
    space_multiplicity = g.sum(i < spacesize)[1]
    # Warn of any duplicate terms in space
    if (space_multiplicity > 1).any():
        warn(
            "Duplicate terms present in search space. Only first instance of each query term\
            will be reported."
        )
    # For query terms in the space, the min combined index will be the first index of that
    # term in the space
    uspaceidx = g.min(i)[1]
    # For query terms not in the space, the min combined index will exceed the space size
    # and should be set to -1
    uspaceidx = where(uspaceidx >= spacesize, -1, uspaceidx)
    # Broadcast unique term indices to combined list of space and query terms
    spaceidx = g.broadcast(uspaceidx)
    # Return only the indices of the query terms (remove the search space)
    return spaceidx[i >= spacesize]


def lookup(keys, values, arguments, fillvalue=-1):
    """
    Apply the function defined by the mapping keys --> values to arguments.

    Parameters
    ----------
    keys : (sequence of) array-like
        The domain of the function. Entries must be unique (if a sequence of
        arrays is given, each row is treated as a tuple-valued entry).
    values : pdarray
        The range of the function. Must be same length as keys.
    arguments : (sequence of) array-like
        The arguments on which to evaluate the function. Must have same dtype
        (or tuple of dtypes, for a sequence) as keys.
    fillvalue : scalar
        The default value to return for arguments not in keys.

    Returns
    -------
    evaluated : pdarray
        The result of evaluating the function over arguments.

    Notes
    -----
    While the values cannot be Strings (or other complex objects), the same
    result can be achieved by passing an arange as the values, then using
    the return as indices into the desired object.

    Examples
    --------
    # Lookup numbers by two-word name
    >>> keys1 = ak.array(['twenty' for _ in range(5)])
    >>> keys2 = ak.array(['one', 'two', 'three', 'four', 'five'])
    >>> values = ak.array([21, 22, 23, 24, 25])
    >>> args1 = ak.array(['twenty', 'thirty', 'twenty'])
    >>> args2 = ak.array(['four', 'two', 'two'])
    >>> aku.lookup([keys1, keys2], values, [args1, args2])
    array([24, -1, 22])

    # Other direction requires an intermediate index
    >>> revkeys = values
    >>> revindices = ak.arange(values.size)
    >>> revargs = ak.array([24, 21, 22])
    >>> idx = aku.lookup(revkeys, revindices, revargs)
    >>> keys1[idx], keys2[idx]
    (array(['twenty', 'twenty', 'twenty']),
    array(['four', 'one', 'two']))
    """
    if isinstance(values, Categorical):
        codes = lookup(keys, values.codes, arguments, fillvalue=values._NAcode)
        return Categorical.from_codes(codes, values.categories, NAvalue=values.NAvalue)
    # Find arguments in keys array
    idx = find(arguments, keys)
    # Initialize return values with fillvalue for missing values
    retvals = full(idx.size, fillvalue, dtype=values.dtype)
    # Where arguments were found in keys, put corresponding fuction values
    found = idx >= 0
    retvals[found] = values[idx[found]]
    return retvals


def in1d_intervals(vals, intervals, symmetric=False):
    """
    Test each value for membership in *any* of a set of half-open (pythonic)
    intervals.

    Parameters
    ----------
    vals : pdarray(int, float)
        Values to test for membership in intervals
    intervals : 2-tuple of pdarrays
        Non-overlapping, half-open intervals, as a tuple of
        (lower_bounds_inclusive, upper_bounds_exclusive)
    symmetric : bool
        If True, also return boolean pdarray indicating which intervals
        contained one or more query values.

    Returns
    -------
    pdarray(bool)
        Array of same length as <vals>, True if corresponding value is
        included in any of the ranges defined by (low[i], high[i]) inclusive.
    pdarray(bool) (if symmetric=True)
        Array of same length as number of intervals, True if corresponding
        interval contains any of the values in <vals>.

    Notes
    -----
    First return array is equivalent to the following:
        ((vals >= intervals[0][0]) & (vals < intervals[1][0])) |
        ((vals >= intervals[0][1]) & (vals < intervals[1][1])) |
        ...
        ((vals >= intervals[0][-1]) & (vals < intervals[1][-1]))
    But much faster when testing many ranges.

    Second (optional) return array is equivalent to:
        ((intervals[0] <= vals[0]) & (intervals[1] > vals[0])) |
        ((intervals[0] <= vals[1]) & (intervals[1] > vals[1])) |
        ...
        ((intervals[0] <= vals[-1]) & (intervals[1] > vals[-1]))
    But much faster when vals is non-trivial size.
    """
    idx = search_intervals(vals, intervals)
    found = idx > -1
    if symmetric:
        containresult = in1d(arange(intervals[0].size), idx)
        return found, containresult
    else:
        return found


def search_intervals(vals, intervals, tiebreak=None):
    """
    Given an array of query vals and closed intervals, return the index of the
    best (see tiebreak) interval containing each query value, or -1 if not present in any
    interval.

    Parameters
    ----------
    vals : (sequence of) pdarray(int, uint, float)
        Values to search for in intervals. If multiple arrays, each "row" is an item.
    intervals : 2-tuple of (sequences of) pdarrays
        Closed (inclusive) intervals, as a tuple of (lower_bounds_inclusive, upper_bounds_inclusive).
        Must have same dtype(s) as vals.
    tiebreak : (optional) pdarray, numeric
        When a value is present in more than one interval, the interval with the
        lowest tiebreak value will be chosen. If no tiebreak is given, the
        first containing interval will be chosen.

    Returns
    -------
    idx : pdarray(int64)
        Index of interval containing each query value, or -1 if not found

    Notes
    -----
    The return idx satisfies the following condition:
        present = idx > -1
        ((intervals[0][idx[present]] <= vals[present]) &
         (intervals[1][idx[present]] >= vals[present])).all()
    """
    from arkouda.join import gen_ranges

    if len(intervals) != 2:
        raise ValueError("intervals must be 2-tuple of (lower_bound_inclusive, upper_bounds_inclusive)")

    low = intervals[0]
    high = intervals[1]
    intervalsize = low.size if isinstance(low, pdarray) else low[0].size
    if tiebreak is None:
        tiebreak = arange(intervalsize)
    elif not isinstance(tiebreak, pdarray) or tiebreak.size != intervalsize:
        raise TypeError("Tiebreak must be pdarray of same size as number of intervals")

    if isinstance(vals, pdarray) and vals.dtype in (akint64, akuint64, akfloat64):
        # argument validation for pdarray
        if not isinstance(low, pdarray) or not isinstance(high, pdarray):
            raise TypeError("intervals must be same objtype as vals")

        # validate the dtypes
        if vals.dtype != low.dtype or vals.dtype != high.dtype:
            raise TypeError(
                f"vals and intervals must all have the same dtype. "
                f"Found {low.dtype}, {high.dtype}, and {vals.dtype}"
            )

        # verify lower and upper bounds are same length
        if low.size != high.size:
            raise ValueError("Lower and upper bound arrays must be same size")
        # verify upper bounds are greater than lower bounds
        if not (high >= low).all():
            raise ValueError("Upper bounds must be greater than lower bounds")

        # Index of interval containing each unique value (initialized to -1: not found)
        containinginterval = -ones(vals.size, dtype=akint64)
        concat = concatenate((low, vals, high))
        perm = argsort(concat)
        # iperm is the indices of the original values in the sorted array
        iperm = argsort(perm)  # aku.invert_permutation(perm)
        boundary = vals.size + low.size
        # indices of the lower bounds in the sorted array
        starts = iperm[: low.size]
        # indices of the upper bounds in the sorted array
        ends = iperm[boundary:]
        # which lower/upper bound pairs have any indices between them?
        valid = ends > starts + 1
        if valid.sum() > 0:
            # pranges is all the indices in sorted array that fall between a lower and an uppper bound
            segs, pranges = gen_ranges(starts[valid] + 1, ends[valid])
            # matches are the indices of those items in the original array
            matches = perm[pranges]
            # integer indices of each interval containing a hit
            hitidx = arange(valid.size)[valid]
            # broadcast interval index out to matches
            matchintervalidx = broadcast(segs, hitidx, matches.size)
            # make sure not to include any of the bounds themselves
            validmatch = (matches >= low.size) & (matches < boundary)
            matchintervalidx = matchintervalidx[validmatch]
            # indices of values found (translated from concat keys)
            validx = matches[validmatch] - low.size
            # break ties for values contained in more than one interval
            byvalidx = GroupBy(validx)
            validx, tmpidx = byvalidx.argmin(tiebreak[matchintervalidx])
            # set index of containing interval for uvals that were found
            containinginterval[validx] = matchintervalidx[tmpidx]
        return containinginterval
    elif isinstance(vals, (list, tuple)):
        # argument validation for multi-array
        if not isinstance(low, (list, tuple)) or not isinstance(high, (list, tuple)):
            raise TypeError("intervals must be same type as vals")
        if len(vals) != len(low) or len(vals) != len(high):
            raise TypeError("Multi-array arguments must have same number of arrays")
        if (
            any([not isinstance(v, pdarray) for v in vals])
            or any([not isinstance(lo, pdarray) for lo in low])
            or any([not isinstance(hi, pdarray) for hi in high])
        ):
            raise TypeError("All elements of Multi-array arguments must be pdarrays")

        valsize = set(v.size for v in vals)
        lowsize = set(lo.size for lo in low)
        highsize = set(hi.size for hi in high)
        if len(valsize) != 1 or len(lowsize) != 1 or len(highsize) != 1:
            raise TypeError("Multi-array arguments must be non-empty and have equal-length arrays")

        # validate the dtypes
        valtypes = np.array([v.dtype for v in vals])
        lowtypes = np.array([lo.dtype for lo in low])
        hightypes = np.array([hi.dtype for hi in high])
        if (valtypes != lowtypes).any() or (valtypes != hightypes).any():
            raise TypeError("Values and intervals must have matching dtypes")

        valsize = valsize.pop()
        lowsize = lowsize.pop()
        highsize = highsize.pop()
        # verify lower and upper bounds are same length
        if lowsize != highsize:
            raise ValueError("Lower and upper bound arrays must be same size")
        # verify upper bounds are greater than lower bounds
        if not all([(hi >= lo).all() for hi, lo in zip(high, low)]):
            raise ValueError("Upper bounds must be greater than lower bounds")

        # Index of interval containing each unique value (initialized to -1: not found)
        containinginterval = -ones(valsize, dtype=akint64)
        concat = [concatenate((lo, v, hi)) for lo, v, hi in zip(low, vals, high)]
        perm = [argsort(c) for c in concat]
        # iperm is the indices of the original values in the sorted array
        iperm = [argsort(p) for p in perm]  # aku.invert_permutation(perm)
        boundary = valsize + lowsize
        # indices of the lower bounds in the sorted array
        starts = [ip[:lowsize] for ip in iperm]
        # indices of the upper bounds in the sorted array
        ends = [ip[boundary:] for ip in iperm]
        # which lower/upper bound pairs have any indices between them?
        # take the logical AND of all elements in list
        valid = functools.reduce(lambda x, y: x & y, [e > s + 1 for e, s in zip(ends, starts)])
        if valid.sum() > 0:
            # pranges is all the indices in sorted array that fall between a lower and
            # an uppper bound for each dimension
            segs, pranges = zip(*[gen_ranges(s[valid] + 1, e[valid]) for s, e in zip(starts, ends)])
            # matches are the indices of those items in the original array
            matches = [pm[pr] for pm, pr in zip(perm, pranges)]
            # integer indices of each one-dimensional interval containing a hit
            hitidx = arange(valid.size)[valid]
            # broadcast 1-d interval index out to matches
            matchintervalidx = [broadcast(s, hitidx, m.size) for s, m in zip(segs, matches)]
            # make sure not to include any of the bounds themselves
            validmatch = [(m >= lowsize) & (m < boundary) for m in matches]
            # indices of values found (translated from concat keys) in 1-d intervals
            uvalidx = [m[vm] - lowsize for m, vm in zip(matches, validmatch)]
            # now go from 1-d to full dimensionality
            # for each interval, intersect the hits from its 1-d projections
            # do this by concatenating all the projections and grouping on the id of the hit
            # and the interval and looking for hits that cover all dimensions
            alluvalidx = concatenate(uvalidx, ordered=False)
            allmatchintervalidx = concatenate(
                [mi[vm] for mi, vm in zip(matchintervalidx, validmatch)], ordered=False
            )
            byvalinterval = GroupBy([alluvalidx, allmatchintervalidx])
            # a true hit happens when a value is contained in all of an interval's 1-d projections
            isahit = byvalinterval.count()[1] == len(low)
            # indices of the true hits and their containing intervals
            valhits, intervalhits = [x[isahit] for x in byvalinterval.unique_keys]
            # a value might be found in more than one interval, so we need to break ties
            byval = GroupBy(valhits)
            hitvalidx, tmpidx = byval.argmin(tiebreak[intervalhits])
            winninginterval = intervalhits[tmpidx]
            # set index of best containing interval for values that were found
            containinginterval[hitvalidx] = winninginterval
            return containinginterval
    else:
        raise TypeError("arguments must be numeric pdarrays or a sequence of numeric pdarrays")


def interval_lookup(keys, values, arguments, fillvalue=-1, tiebreak=None):
    """
    Apply a function defined over intervals to an array of arguments.

    Parameters
    ----------
    keys : 2-tuple of (sequences of) pdarrays
        Tuple of closed intervals expressed as (lower_bounds_inclusive, upper_bounds_inclusive).
        Must have same dtype(s) as vals.
    values : pdarray
        Function value to return for each entry in keys.
    arguments : (sequences of) pdarray
        Values to search for in intervals. If multiple arrays, each "row" is an item.
    fillvalue : scalar
        Default value to return when argument is not in any interval.
    tiebreak : (optional) pdarray, numeric
        When an argument is present in more than one key interval, the interval with the
        lowest tiebreak value will be chosen. If no tiebreak is given, the
        first valid key interval will be chosen.

    Returns
    -------
    pdarray
        Value of function corresponding to the keys interval
        containing each argument, or fillvalue if argument not
        in any interval.
    """
    if isinstance(values, Categorical):
        codes = interval_lookup(keys, values.codes, arguments, fillvalue=values._NAcode)
        return Categorical.from_codes(codes, values.categories, NAvalue=values.NAvalue)
    idx = search_intervals(arguments, keys, tiebreak=tiebreak)
    arguments_size = arguments.size if isinstance(arguments, pdarray) else arguments[0].size
    res = zeros(arguments_size, dtype=values.dtype)
    if fillvalue is not None:
        res.fill(fillvalue)
    found = idx > -1
    res[found] = values[idx[found]]
    return res
