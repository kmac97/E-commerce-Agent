# api/rate_limit.py
# Shared rate limiter for the expensive / externally-costed dashboard endpoints
# (research, product import, competitor spy, Shopify draft creation, chat).
#
# ponytail: this is a single-operator system with exactly one legitimate
# caller (you, via the dashboard's one API key). Limits are global per-route
# (one shared bucket for every caller) rather than per-IP -- the goal is
# capping total spend if the key ever leaks, not fairness between clients.
# Upgrade to per-key/per-IP limiting if this ever becomes multi-tenant.

from slowapi import Limiter


def _global_key(request) -> str:
    return "global"


limiter = Limiter(key_func=_global_key)
