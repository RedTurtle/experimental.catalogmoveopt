"""Monkey-patches applied to Products.CMFCore at Zope startup.

Two changes are made:

1. ``handleContentishEvent`` is replaced with a version that, on a true object
   move, skips the full unindex + reindex cycle and instead calls
   ``CatalogTool.moveObject`` to remap the catalog RID and reindex only the
   context-aware indexes.

2. ``CatalogTool.moveObject`` is injected (it does not exist in stock CMFCore).

The replacement is functionally identical to the original for every event type
except ``IObjectWillBeMovedEvent`` and ``IObjectMovedEvent`` on true moves.

The old path is stored via ``Transaction.set_data`` / ``Transaction.data``
(keyed by a module-level singleton) rather than a volatile ``_v_`` attribute,
making it immune to ZODB cache eviction (ghostification) for large subtrees.
See ``_pending_move_paths()`` for details.
"""

from .providers import get_context_aware_indexes
from Acquisition import aq_base
from OFS.interfaces import IObjectWillBeMovedEvent
from zope.component import getGlobalSiteManager
from zope.component import queryUtility
from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectCopiedEvent
from zope.lifecycleevent.interfaces import IObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectMovedEvent

import transaction


# ---------------------------------------------------------------------------
# Transaction-local registry for in-flight move paths
# ---------------------------------------------------------------------------


class _MovePathsRegistryKey:
    """Singleton used as key for ``transaction.set_data`` /
    ``transaction.data``.

    The ``transaction`` package stores arbitrary per-transaction data via
    ``Transaction.set_data(ob, value)`` / ``Transaction.data(ob)``, keyed by
    the identity (``id``) of *ob*.  Using a module-level singleton that is
    never garbage-collected gives a stable, collision-free key.
    """


_MOVE_PATHS_KEY = _MovePathsRegistryKey()


def _pending_move_paths():
    """Return the transaction-local dict ``{oid: old_path}`` for in-flight
    moves.

    On ``IObjectWillBeMovedEvent`` each object's current physical path is
    recorded here, keyed by its ZODB ``_p_oid``.  On ``IObjectMovedEvent``
    the entry is popped and used to call ``CatalogTool.moveObject``.

    Stored via ``Transaction.set_data`` rather than as a volatile ``_v_``
    attribute because volatile attributes are discarded on ZODB ghostification.
    For large subtrees this caused silent fallback to a full reindex for all
    objects evicted from the cache between the two event phases.
    Transaction-attached data lives outside the ZODB object graph, is never
    affected by cache pressure, and is discarded automatically on commit/abort.
    """
    txn = transaction.get()
    try:
        return txn.data(_MOVE_PATHS_KEY)
    except KeyError:
        registry = {}
        txn.set_data(_MOVE_PATHS_KEY, registry)
        return registry


# ---------------------------------------------------------------------------
# Replacement event subscriber
# ---------------------------------------------------------------------------


def _handle_object_moved(ob, event):
    from Products.CMFCore.interfaces import ICatalogTool

    if event.newParent is None:
        return
    oid = getattr(ob, "_p_oid", None)
    old_path = _pending_move_paths().pop(oid, None) if oid else None
    if old_path is not None:
        catalog = queryUtility(ICatalogTool)
        if catalog is not None:
            if hasattr(aq_base(ob), "notifyModified"):
                ob.notifyModified()
            catalog.moveObject(ob, old_path, get_context_aware_indexes())
            return
    ob.indexObject()


def _handle_object_will_be_moved(ob, event):
    from Products.CMFCore.interfaces import ICatalogTool

    if event.oldParent is None:
        return
    if event.newParent is not None:
        catalog = queryUtility(ICatalogTool)
        idxs = get_context_aware_indexes()
        if catalog is not None and idxs:
            oid = getattr(ob, "_p_oid", None)
            if oid is not None:
                _pending_move_paths()[oid] = "/".join(ob.getPhysicalPath())
                return  # skip unindexObject; catalog entry preserved
    ob.unindexObject()


def handleContentishEvent(ob, event):
    """Replacement for ``Products.CMFCore.CMFCatalogAware.handleContentishEvent``.

    Identical to the original for all event types except true object moves,
    where it uses the optimized ``CatalogTool.moveObject`` path.
    """
    from Products.CMFCore.interfaces import IWorkflowAware

    if IObjectAddedEvent.providedBy(event):
        wfaware = IWorkflowAware(ob, None)
        if wfaware is not None:
            wfaware.notifyWorkflowCreated()
        ob.indexObject()
    elif IObjectMovedEvent.providedBy(event):
        _handle_object_moved(ob, event)
    elif IObjectWillBeMovedEvent.providedBy(event):
        _handle_object_will_be_moved(ob, event)
    elif IObjectCopiedEvent.providedBy(event):
        if hasattr(aq_base(ob), "workflow_history"):
            del ob.workflow_history
    elif IObjectCreatedEvent.providedBy(event):
        if hasattr(aq_base(ob), "addCreator"):
            ob.addCreator()


# ---------------------------------------------------------------------------
# CatalogTool.moveObject implementation
# ---------------------------------------------------------------------------


def _catalog_tool_move_object(self, obj, old_path, idxs):
    """Update the catalog when ``obj`` is moved, preserving its RID.

    Flushes the index queue, remaps the old path to the same RID at the new
    path, and reindexes only ``idxs``.  Injected into ``CatalogTool`` by
    ``apply_patches()``.
    """
    from Products.CMFCore.indexing import getQueue

    getQueue().process()

    new_path = "/".join(obj.getPhysicalPath())
    cat = self._catalog
    rid = cat.uids.get(old_path)

    if rid is None:
        # Object not yet in catalog (added and moved in the same transaction;
        # INDEX already ran at the new path via queue.process()).
        self.reindexObject(obj, idxs=list(idxs), update_metadata=1)
        return

    # Remap old path → same RID → new path (preserves RID).
    cat.uids[new_path] = rid
    cat.paths[rid] = new_path
    if old_path in cat.uids:
        del cat.uids[old_path]

    self.reindexObject(obj, idxs=list(idxs), update_metadata=1)


# ---------------------------------------------------------------------------
# Patch application — called from the IProcessStarting subscriber
# ---------------------------------------------------------------------------


#: The genuine ``CMFCatalogAware.handleContentishEvent`` captured the first time
#: ``apply_patches()`` runs, before we overwrite the module attribute with ours.
#: Kept so that subsequent (idempotent) calls can still target the stock handler
#: for unregistration.
_stock_handler = None


def _registry_chain(registry):
    """Yield *registry* and all of its transitive bases, each exactly once.

    Subscriber registrations are looked up across the whole base chain, but
    ``unregisterHandler`` only removes a registration from the registry that
    holds it directly.  Under the stacked global registries used by
    ``plone.testing`` the stock handler is registered in a *base* of the current
    global site manager, so removing it requires walking the chain.  In
    production the chain is just the single global registry.
    """
    seen = []
    stack = [registry]
    while stack:
        reg = stack.pop()
        if any(reg is s for s in seen):
            continue
        seen.append(reg)
        yield reg
        stack.extend(getattr(reg, "__bases__", ()))


def apply_patches():
    """Unregister the original ``handleContentishEvent`` and register ours.

    Also injects ``CatalogTool.moveObject`` if not already present.

    Called via the ``IProcessStarting`` subscriber in ``configure.zcml``,
    after all ZCML has been processed and the original subscriber is already
    registered in the GSM.
    """
    global _stock_handler

    from AccessControl.class_init import InitializeClass
    from AccessControl.SecurityInfo import ClassSecurityInfo
    from Products.CMFCore import CMFCatalogAware
    from Products.CMFCore.CatalogTool import CatalogTool
    from Products.CMFCore.interfaces import IContentish
    from zope.interface.interfaces import IObjectEvent

    current = CMFCatalogAware.handleContentishEvent
    if current is not handleContentishEvent:
        # First time we patch (or someone restored the stock handler): remember
        # the genuine stock callable so we can keep removing it on later calls.
        _stock_handler = current

    gsm = getGlobalSiteManager()

    # Remove the stock handler (and any stale copy of ours) from every registry
    # in the lookup chain, then register ours exactly once in the current GSM.
    # Walking the chain is required because under plone.testing's stacked global
    # registries the stock handler lives in a base, where a plain
    # ``gsm.unregisterHandler`` would never find it — leaving both handlers
    # active and causing a full reindex (RID churn) on every move.
    targets = [t for t in (_stock_handler, handleContentishEvent) if t is not None]
    for reg in _registry_chain(gsm):
        for target in targets:
            reg.unregisterHandler(target, (IContentish, IObjectEvent))

    gsm.registerHandler(handleContentishEvent, (IContentish, IObjectEvent))

    # Keep the module attribute in sync so that a second call to apply_patches()
    # will find *our* handler (not the original) when calling unregisterHandler,
    # making this function safely idempotent.
    CMFCatalogAware.handleContentishEvent = handleContentishEvent

    if not hasattr(CatalogTool, "moveObject"):
        security = ClassSecurityInfo()
        security.declarePrivate("moveObject")
        CatalogTool.moveObject = _catalog_tool_move_object
        InitializeClass(CatalogTool)
