"""Module where all interfaces, events and exceptions live."""

from zope.interface import Interface


class IContextAwareIndexProvider(Interface):
    """Named utility contributing catalog index names that must be reindexed
    when an object moves within the content tree.

    Register a named utility providing this interface to add custom
    location- or security-sensitive indexes.  Use your package's dotted name
    as the utility name (e.g. ``"mypackage.myindex"``) to avoid conflicts.
    All registered providers are aggregated by
    ``experimental.catalogmoveopt.providers.get_context_aware_indexes()``.
    """

    def getIndexNames():
        """Return a sequence of context-aware catalog index names.

        These are indexes whose values change when an object moves to a
        different location in the content tree (path, id, security context,
        etc.).

        o Return a sequence (tuple or list) of strings.
        o Permission: Private (Python only)
        """
