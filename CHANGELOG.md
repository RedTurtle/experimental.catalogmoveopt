# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

## 1.0.0a2 (2026-10-02)


### Breaking changes:

- Align with the updated upstream Products.CMFCore#161: every index is now reindexed on move, except the ones listed in the `contextless_indexes` property of `portal_catalog`.
  `IContextAwareIndexProvider` and the built-in providers are removed.
  `CatalogTool.moveObject(object, old_path)` no longer takes `idxs`, updates the modification date and returns `True`/`False`.
  The indexing queue is flushed before a move, and a leftover catalog entry at the new path is dropped.
  Catalogs without `moveObject` keep the stock unindex + index behavior. 


### New features:

- Skip `SearchableText` on move by default, even without installing a profile: it applies when `portal_catalog` has no `contextless_indexes` property. An empty property opts out.
  Add the `experimental.catalogmoveopt:default` GenericSetup profile, which sets the property explicitly, and an `uninstall` profile that sets it empty. 

## 1.0.0a1 (2026-06-10)


### Bug fixes:

- add args to subscriber IProcessStarting 

## 1.0.0a0 (2026-06-10)


### New features:

- Call notifyModified() on optimized move path and reindex modified/Date indexes (parity with ftw.copymovepatches; ensures caches keyed on modification date are invalidated when objects are moved)
  Add cmf.temporal IContextAwareIndexProvider (modified, Date) [#1](https://github.com/RedTurtle/experimental.catalogmoveopt/issues/1)
