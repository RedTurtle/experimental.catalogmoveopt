from .interfaces import IContextAwareIndexProvider
from zope.component import getUtilitiesFor
from zope.interface import implementer


@implementer(IContextAwareIndexProvider)
class _BuiltinLocationIndexProvider:
    """Default provider for location-based context-aware indexes.

    These indexes change when an object moves to a different container
    (its path and id change).
    """

    def getIndexNames(self):
        return ("path", "getId", "id")


@implementer(IContextAwareIndexProvider)
class _BuiltinSecurityIndexProvider:
    """Default provider for security context-aware indexes.

    allowedRolesAndUsers must be recomputed whenever the object moves
    into a differently-protected part of the tree.
    """

    def getIndexNames(self):
        return ("allowedRolesAndUsers",)


@implementer(IContextAwareIndexProvider)
class _BuiltinTemporalIndexProvider:
    """Default provider for modification-date context-aware indexes.

    Moving an object changes its context (path, security tree), which is a
    meaningful content change from the perspective of caches and change-tracking
    systems.  Updating ``modified`` / ``Date`` on move ensures that cache keys
    built on modification dates are correctly invalidated.
    """

    def getIndexNames(self):
        return ("modified", "Date")


#: Module-level singletons registered as named utilities in configure.zcml.
builtin_location_provider = _BuiltinLocationIndexProvider()
builtin_security_provider = _BuiltinSecurityIndexProvider()
builtin_temporal_provider = _BuiltinTemporalIndexProvider()


def get_context_aware_indexes():
    """Return frozenset of all context-aware catalog index names.

    Aggregates all named IContextAwareIndexProvider utilities registered in
    the global site manager.  Returns an empty frozenset if no providers are
    registered (which disables the optimization).
    """
    indexes = set()
    for _name, provider in getUtilitiesFor(IContextAwareIndexProvider):
        indexes.update(provider.getIndexNames())
    return frozenset(indexes)
