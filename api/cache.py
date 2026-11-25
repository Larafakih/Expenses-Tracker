"""Caching for the expense list endpoint (GET /expenses/).

Invalidation uses a per-user "version" number instead of deleting keys:

    expenses:list:user:<id>:v<version>:<hash of host + query params>

Every page/filter/search/ordering combination gets its own key. When anything
that appears in the list changes, we bump the user's version: all the old keys
stop being read and Redis expires them on their own (TIMEOUT). This avoids
having to find and delete every page/filter combination one by one.
"""
import hashlib
import logging
import time
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

EXPENSE_LIST_TIMEOUT = 60 * 5  # seconds; safety net in case an invalidation is missed


def _version_key(user_id):
    return f"expenses:list:user:{user_id}:version"


def _get_version(user_id):
    # Start from the current time (not 1): if the version key is ever evicted,
    # the new version can't collide with an old one whose list entries still exist.
    # timeout=None: the version itself never expires.
    return cache.get_or_set(_version_key(user_id), time.time_ns(), timeout=None)


def expense_list_cache_key(request):
    # Sort the params so ?a=1&b=2 and ?b=2&a=1 share a cache entry.
    # The host is included because pagination "next"/"previous" are absolute URLs.
    params = urlencode(sorted(request.query_params.lists()), doseq=True)
    digest = hashlib.md5(f"{request.get_host()}?{params}".encode()).hexdigest()
    user_id = request.user.pk
    return f"expenses:list:user:{user_id}:v{_get_version(user_id)}:{digest}"


def get_cached_expense_list(request):
    """Return (key, data). data is None on a miss. Never raises if Redis is down."""
    try:
        key = expense_list_cache_key(request)
        return key, cache.get(key)
    except Exception:
        logger.warning("Expense list cache read failed", exc_info=True)
        return None, None


def set_cached_expense_list(key, data):
    if key is None:
        return
    try:
        cache.set(key, data, EXPENSE_LIST_TIMEOUT)
    except Exception:
        logger.warning("Expense list cache write failed", exc_info=True)


def _bump_version(user_id):
    try:
        cache.incr(_version_key(user_id))
    except ValueError:
        # Key missing (never read, or evicted): any new value is a fresh version.
        cache.set(_version_key(user_id), time.time_ns(), timeout=None)
    except Exception:
        logger.warning("Expense list cache invalidation failed for user %s", user_id, exc_info=True)


def invalidate_expense_list(*user_ids):
    """Mark the cached expense lists of these users as stale.

    Runs after the current transaction commits: if we bumped the version before
    the commit, a request in between could read the old rows from the database
    and cache them under the new version.
    """
    for user_id in {uid for uid in user_ids if uid is not None}:
        transaction.on_commit(lambda uid=user_id: _bump_version(uid))
