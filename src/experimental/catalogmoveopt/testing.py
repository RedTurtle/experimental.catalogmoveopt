from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer

import experimental.catalogmoveopt


class Layer(PloneSandboxLayer):
    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=experimental.catalogmoveopt)
        # In the test environment IProcessStarting fires at Zope startup,
        # before setUpZope runs, so our subscriber was not yet registered
        # when the event fired.  Apply the patches explicitly here.
        from experimental.catalogmoveopt.patches import apply_patches

        apply_patches()


FIXTURE = Layer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name="Experimental.CatalogmoveoptLayer:IntegrationTesting",
)
