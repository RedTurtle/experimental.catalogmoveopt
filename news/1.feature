Call notifyModified() on optimized move path and reindex modified/Date indexes (parity with ftw.copymovepatches; ensures caches keyed on modification date are invalidated when objects are moved)
Add cmf.temporal IContextAwareIndexProvider (modified, Date)
