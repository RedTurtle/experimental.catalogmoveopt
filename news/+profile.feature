Skip `SearchableText` on move by default, even without installing a profile: it applies when `portal_catalog` has no `contextless_indexes` property. An empty property opts out.
Add the `experimental.catalogmoveopt:default` GenericSetup profile, which sets the property explicitly, and an `uninstall` profile that sets it empty.
