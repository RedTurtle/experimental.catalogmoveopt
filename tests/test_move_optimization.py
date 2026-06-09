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
            plone.api.content.move(source=doc, target=target_folder)

        new_rid = _rid(catalog, doc)
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
            plone.api.content.move(source=doc, target=target_folder)

        new_path = "/".join(doc.getPhysicalPath())
        assert catalog._catalog.uids.get(new_path) is not None


class TestOnlyContextAwareIndexesReindexed:
    def test_rename_reindexes_only_declared_indexes(self, portal, doc, integration):
        """reindexObject is called with only the context-aware index set."""
        from Products.CMFCore.utils import getToolByName
        from unittest.mock import patch

        import plone.api

        catalog = getToolByName(portal, "portal_catalog")
        reindex_calls = []

        original = catalog.reindexObject

        def capturing_reindex(obj, idxs=None, update_metadata=0):
            reindex_calls.append(list(idxs or []))
            return original(obj, idxs=idxs, update_metadata=update_metadata)

        with (
            patch.object(catalog, "reindexObject", capturing_reindex),
            plone.api.env.adopt_roles(["Manager"]),
        ):
            plone.api.content.rename(obj=doc, new_id="test-doc-renamed")

        # The optimized path should call reindexObject exactly once with the
        # context-aware indexes only (path, getId, id, allowedRolesAndUsers).
        assert len(reindex_calls) == 1
        reindexed = frozenset(reindex_calls[0])
        expected = frozenset(("path", "getId", "id", "allowedRolesAndUsers"))
        assert reindexed == expected


class TestFallbackOnNoOid:
    def test_object_without_oid_falls_back_to_full_reindex(self, portal, integration):
        """When an object has no _p_oid the fallback full reindex is used."""
        from experimental.catalogmoveopt.patches import handleContentishEvent
        from OFS.interfaces import IObjectWillBeMovedEvent
        from unittest.mock import MagicMock
        from unittest.mock import patch
        from zope.lifecycleevent.interfaces import IObjectMovedEvent

        ob = MagicMock()
        ob._p_oid = None  # no OID

        # WillBeMoved: object has no oid → unindexObject must be called
        will_be_moved = MagicMock(spec=IObjectWillBeMovedEvent)
        will_be_moved.oldParent = MagicMock()
        will_be_moved.newParent = MagicMock()
        IObjectWillBeMovedEvent.providedBy = lambda e: e is will_be_moved
        IObjectMovedEvent.providedBy = lambda e: False

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
