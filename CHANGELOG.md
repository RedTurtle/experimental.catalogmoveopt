# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

## 1.0.0a0 (2026-06-10)


### New features:

- Call notifyModified() on optimized move path and reindex modified/Date indexes (parity with ftw.copymovepatches; ensures caches keyed on modification date are invalidated when objects are moved)
  Add cmf.temporal IContextAwareIndexProvider (modified, Date) [#1](https://github.com/RedTurtle/experimental.catalogmoveopt/issues/1)
