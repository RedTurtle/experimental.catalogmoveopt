"""Integration tests: RID preservation and selective reindex on move/rename."""

import pytest


@pytest.fixture
def folder(portal, integration):
    """A Folder at /plone/test-folder."""
    import plone.api

    with plone.api.env.adopt_roles(["Manager"]):
        obj = plone.api.content.create(
            container=portal,
            type="Folder",
            id="test-folder",
            title="Test Folder",
        )
    return obj


@pytest.fixture
def doc(portal, folder, integration):
    """A Document inside the test folder."""
    import plone.api

    with plone.api.env.adopt_roles(["Manager"]):
        obj = plone.api.content.create(
            container=folder,
            type="Document",
            id="test-doc",
            title="Test Document",
        )
    return obj


@pytest.fixture
def target_folder(portal, integration):
    """A second Folder used as cut-paste destination."""
    import plone.api

    with plone.api.env.adopt_roles(["Manager"]):
        obj = plone.api.content.create(
            container=portal,
            type="Folder",
            id="target-folder",
            title="Target Folder",
        )
    return obj


def _rid(catalog, obj):
    """Return the RID of *obj* in the catalog, or None if not found."""
    path = "/".join(obj.getPhysicalPath())
    return catalog._catalog.uids.get(path)


class TestRenamePreservesRid:
    def test_rid_unchanged_after_rename(self, portal, doc, integration):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        old_rid = _rid(catalog, doc)
        assert old_rid is not None, "doc must be indexed before rename"

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        new_rid = _rid(catalog, doc)
        assert new_rid == old_rid, "RID must be preserved after rename"

    def test_old_path_removed_after_rename(self, portal, doc, integration):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        old_path = "/".join(doc.getPhysicalPath())

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        assert catalog._catalog.uids.get(old_path) is None

    def test_new_path_findable_after_rename(self, portal, doc, integration):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        new_path = "/".join(doc.getPhysicalPath())
        assert catalog._catalog.uids.get(new_path) is not None
        brains = catalog(path={"query": new_path, "depth": 0})
        assert len(brains) == 1


class TestCutPastePreservesRid:
    def test_rid_unchanged_after_move(self, portal, doc, target_folder, integration):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        old_rid = _rid(catalog, doc)
        assert old_rid is not None, "doc must be indexed before move"

        with plone.api.env.adopt_roles(["Manager"]):
            # A cross-container move returns a new object at the target; the
            # original ``doc`` reference is left detached (its parent still
            # points at the old folder), so use the returned object.
            moved = plone.api.content.move(source=doc, target=target_folder)

        new_rid = _rid(catalog, moved)
        assert new_rid == old_rid, "RID must be preserved after cut-paste"

    def test_old_path_removed_after_move(self, portal, doc, target_folder, integration):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        old_path = "/".join(doc.getPhysicalPath())

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.move(source=doc, target=target_folder)

        assert catalog._catalog.uids.get(old_path) is None

    def test_new_path_findable_after_move(
        self, portal, doc, target_folder, integration
    ):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")

        with plone.api.env.adopt_roles(["Manager"]):
            moved = plone.api.content.move(source=doc, target=target_folder)

        new_path = "/".join(moved.getPhysicalPath())
        assert catalog._catalog.uids.get(new_path) is not None


def _capture_reindex(catalog, obj):
    """Patch context manager helper: record ``idxs`` of reindexes of *obj*."""
    from Acquisition import aq_base
    from unittest.mock import patch

    obj_base = aq_base(obj)
    calls = []
    original = catalog.reindexObject

    # ``CMFCatalogAware.reindexObject`` forwards a ``uid`` keyword to the
    # catalog tool, so the wrapper must accept it.  Only calls for the moved
    # object are recorded (renaming a child also reindexes the container).
    def capturing_reindex(o, idxs=None, update_metadata=0, uid=None):
        if aq_base(o) is obj_base:
            calls.append(frozenset(idxs or ()))
        return original(o, idxs=idxs, update_metadata=update_metadata, uid=uid)

    return calls, patch.object(catalog, "reindexObject", capturing_reindex)


class TestContextlessIndexes:
    def test_rename_skips_contextless_indexes(self, portal, doc, integration):
        """With the profile installed, SearchableText is not reindexed."""
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        calls, patcher = _capture_reindex(catalog, doc)

        with patcher, plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        moved = [c for c in calls if "SearchableText" not in c and "path" in c]
        assert moved, f"move must reindex all but contextless indexes; got {calls}"
        assert frozenset(catalog.indexes()) - moved[0] == {"SearchableText"}
        # Never a full reindex (empty idxs == all indexes).
        assert all(calls), f"move must not full-reindex the object; got {calls}"

    def test_rename_skips_default_without_property(self, portal, doc, integration):
        """Without the property (no profile) SearchableText is still skipped."""
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        catalog.manage_delProperties(["contextless_indexes"])
        calls, patcher = _capture_reindex(catalog, doc)

        with patcher, plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        assert frozenset(catalog.indexes()) - {"SearchableText"} in calls

    def test_rename_reindexes_all_with_empty_property(self, portal, doc, integration):
        """An empty ``contextless_indexes`` opts out: every index is reindexed."""
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        catalog.manage_changeProperties(contextless_indexes=[])
        calls, patcher = _capture_reindex(catalog, doc)

        with patcher, plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        assert frozenset(catalog.indexes()) in calls

    def test_skipped_index_keeps_value_on_move(self, portal, doc, integration):
        from Products.CMFCore.utils import getToolByName

        import plone.api

        from Products.CMFCore.indexing import processQueue

        catalog = getToolByName(portal, "portal_catalog")
        processQueue()
        rid = _rid(catalog, doc)
        index = catalog._catalog.getIndex("SearchableText")
        # Make the stored value differ from the object's, then move.
        before = index.getEntryForObject(rid)
        doc.title = "Changed without reindex"

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        assert before
        assert index.getEntryForObject(rid) == before

    def test_move_updates_modification_date(self, portal, doc, integration):
        import plone.api

        before = doc.modified()

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        assert doc.modified() > before


class TestMoveObject:
    def test_returns_false_when_not_cataloged(self, portal, doc, integration):
        from Products.CMFCore.utils import getToolByName

        catalog = getToolByName(portal, "portal_catalog")
        assert catalog.moveObject(doc, "/plone/nowhere") is False

    def test_drops_stale_entry_at_new_path(self, portal, doc, integration):
        from Products.CMFCore.utils import getToolByName

        catalog = getToolByName(portal, "portal_catalog")
        new_path = "/".join(doc.getPhysicalPath())
        old_path = "/plone/old-doc"
        rid = _rid(catalog, doc)
        # Pretend doc was cataloged at old_path, with a leftover at new_path.
        catalog._catalog.uids[old_path] = rid
        catalog._catalog.uids.pop(new_path)
        catalog.catalog_object(doc, new_path)
        stale_rid = catalog._catalog.uids[new_path]
        assert stale_rid != rid

        assert catalog.moveObject(doc, old_path) is True

        assert catalog._catalog.uids[new_path] == rid
        assert old_path not in catalog._catalog.uids
        assert stale_rid not in catalog._catalog.paths


class TestFallbackWithoutMoveObject:
    def test_catalog_without_moveObject_unindexes(self, portal, integration):
        """Catalogs lacking ``moveObject`` keep the stock unindex + index."""
        from experimental.catalogmoveopt.patches import handleContentishEvent
        from OFS.interfaces import IObjectWillBeMovedEvent
        from Products.CMFCore.interfaces import ICatalogTool
        from unittest.mock import MagicMock
        from zope.component import getSiteManager
        from zope.interface import implementer

        @implementer(ICatalogTool)
        class NoMoveCatalog:
            pass

        sm = getSiteManager()
        original = sm.getUtility(ICatalogTool)
        sm.registerUtility(NoMoveCatalog(), ICatalogTool)
        try:
            ob = MagicMock()
            ob._p_oid = b"\x00" * 8

            @implementer(IObjectWillBeMovedEvent)
            class Event:
                oldParent = object()
                newParent = object()

            event = Event()

            handleContentishEvent(ob, event)
        finally:
            sm.registerUtility(original, ICatalogTool)

        ob.unindexObject.assert_called_once()


class TestFallbackOnNoOid:
    def test_object_without_oid_falls_back_to_full_reindex(self, portal, integration):
        """When an object has no _p_oid the fallback full reindex is used."""
        from experimental.catalogmoveopt.patches import handleContentishEvent
        from OFS.interfaces import IObjectWillBeMovedEvent
        from unittest.mock import MagicMock
        from unittest.mock import patch

        ob = MagicMock()
        ob._p_oid = None  # no OID

        # WillBeMoved: object has no oid → unindexObject must be called
        will_be_moved = MagicMock(spec=IObjectWillBeMovedEvent)
        will_be_moved.oldParent = MagicMock()
        will_be_moved.newParent = MagicMock()

        with (
            patch(
                "experimental.catalogmoveopt.patches.IObjectWillBeMovedEvent"
            ) as mock_will,
            patch(
                "experimental.catalogmoveopt.patches.IObjectMovedEvent"
            ) as mock_moved,
            patch(
                "experimental.catalogmoveopt.patches.IObjectAddedEvent"
            ) as mock_added,
            patch(
                "experimental.catalogmoveopt.patches.IObjectCopiedEvent"
            ) as mock_copied,
            patch(
                "experimental.catalogmoveopt.patches.IObjectCreatedEvent"
            ) as mock_created,
        ):
            mock_added.providedBy.return_value = False
            mock_moved.providedBy.return_value = False
            mock_will.providedBy.return_value = True
            mock_copied.providedBy.return_value = False
            mock_created.providedBy.return_value = False
            will_be_moved.oldParent = object()
            will_be_moved.newParent = object()

            handleContentishEvent(ob, will_be_moved)

        ob.unindexObject.assert_called_once()


class TestPendingQueue:
    def test_rename_with_pending_reindex_leaves_single_entry(
        self, portal, doc, integration
    ):
        """A reindex queued before the rename must not create a second entry."""
        from Products.CMFCore.indexing import processQueue
        from Products.CMFCore.utils import getToolByName

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        processQueue()
        rid = _rid(catalog, doc)
        doc.reindexObject()  # queued, not yet processed

        with plone.api.env.adopt_roles(["Manager"]):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")
        processQueue()

        cat = catalog._catalog
        assert len(cat.uids) == len(cat.paths)
        assert _rid(catalog, doc) == rid
