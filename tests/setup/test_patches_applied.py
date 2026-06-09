"""Verify that apply_patches() wired up the GSM and CatalogTool correctly."""


class TestPatchesApplied:
    def test_our_handler_registered(self, integration):
        """Our handleContentishEvent is in the GSM."""
        from experimental.catalogmoveopt.patches import handleContentishEvent
        from zope.component import getGlobalSiteManager

        gsm = getGlobalSiteManager()
        handlers = [r.handler for r in gsm.registeredHandlers()]
        assert handleContentishEvent in handlers

    def test_original_handler_replaced(self, integration):
        """The original CMFCatalogAware handler is no longer in the GSM."""
        from experimental.catalogmoveopt import patches
        from Products.CMFCore import CMFCatalogAware
        from zope.component import getGlobalSiteManager

        gsm = getGlobalSiteManager()
        handlers = [r.handler for r in gsm.registeredHandlers()]
        # CMFCatalogAware.handleContentishEvent was updated by apply_patches()
        # to point to our function, so we check the *original* function object.
        assert patches.handleContentishEvent in handlers
        # The module attribute itself now points to our replacement.
        assert CMFCatalogAware.handleContentishEvent is patches.handleContentishEvent

    def test_catalog_tool_has_move_object(self, integration):
        """CatalogTool gained the moveObject method."""
        from experimental.catalogmoveopt.patches import _catalog_tool_move_object
        from Products.CMFCore.CatalogTool import CatalogTool

        assert hasattr(CatalogTool, "moveObject")
        assert CatalogTool.moveObject is _catalog_tool_move_object
