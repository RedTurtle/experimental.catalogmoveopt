"""Unit tests for get_context_aware_indexes() and IContextAwareIndexProvider."""

from experimental.catalogmoveopt.interfaces import IContextAwareIndexProvider
from experimental.catalogmoveopt.providers import _BuiltinLocationIndexProvider
from experimental.catalogmoveopt.providers import _BuiltinSecurityIndexProvider
from experimental.catalogmoveopt.providers import get_context_aware_indexes
from zope.component import getGlobalSiteManager
from zope.interface import implementer

import pytest


@implementer(IContextAwareIndexProvider)
class _CustomProvider:
    def getIndexNames(self):
        return ("my_custom_index",)


@pytest.fixture(autouse=True)
def clean_gsm():
    """Ensure no stray test utilities leak between tests."""
    yield
    gsm = getGlobalSiteManager()
    for name in ("_test.location", "_test.security", "_test.custom"):
        gsm.unregisterUtility(provided=IContextAwareIndexProvider, name=name)


class TestGetContextAwareIndexes:
    def test_empty_when_no_providers(self):
        """With no utilities registered the result is an empty frozenset."""
        assert get_context_aware_indexes() == frozenset()

    def test_location_provider_indexes(self):
        gsm = getGlobalSiteManager()
        provider = _BuiltinLocationIndexProvider()
        gsm.registerUtility(provider, IContextAwareIndexProvider, "_test.location")
        result = get_context_aware_indexes()
        assert "path" in result
        assert "getId" in result
        assert "id" in result

    def test_security_provider_indexes(self):
        gsm = getGlobalSiteManager()
        provider = _BuiltinSecurityIndexProvider()
        gsm.registerUtility(provider, IContextAwareIndexProvider, "_test.security")
        result = get_context_aware_indexes()
        assert "allowedRolesAndUsers" in result

    def test_providers_merged(self):
        """Indexes from multiple providers are merged into one frozenset."""
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            _BuiltinLocationIndexProvider(),
            IContextAwareIndexProvider,
            "_test.location",
        )
        gsm.registerUtility(
            _BuiltinSecurityIndexProvider(),
            IContextAwareIndexProvider,
            "_test.security",
        )
        result = get_context_aware_indexes()
        assert result >= frozenset(("path", "getId", "id", "allowedRolesAndUsers"))

    def test_custom_provider_included(self):
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            _CustomProvider(), IContextAwareIndexProvider, "_test.custom"
        )
        result = get_context_aware_indexes()
        assert "my_custom_index" in result

    def test_result_is_frozenset(self):
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            _BuiltinLocationIndexProvider(),
            IContextAwareIndexProvider,
            "_test.location",
        )
        assert isinstance(get_context_aware_indexes(), frozenset)
