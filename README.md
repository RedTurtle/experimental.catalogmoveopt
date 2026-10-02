# experimental.catalogmoveopt

Plone add-on that optimizes catalog operations when content is moved or renamed,
preserving Record IDs (RIDs) and reindexing only the indexes that actually change.

## The problem

When an object is moved or renamed in stock Plone, `Products.CMFCore` fires a
full catalog cycle: **unindex at the old path, reindex everything at the new
path**.  For large content trees this is expensive because every index is
recomputed even though most of them (title, description, content body, …) have
not changed at all.  It also assigns a new RID to the object, which can
invalidate in-flight catalog references.

## How it works

The add-on monkey-patches `Products.CMFCore` at Zope startup (via an
`IProcessStarting` subscriber) to replace the stock `handleContentishEvent`
with an optimized version.

On a true object move (old parent ≠ new parent, i.e. cut-paste):

1. **`IObjectWillBeMovedEvent`** — instead of calling `unindexObject()`, the
   indexing queue is flushed (queued objects still report their old path) and
   the object's current physical path is saved in the transaction-local
   registry keyed by its ZODB `_p_oid`.  The catalog entry is left untouched.
2. **`IObjectMovedEvent`** — the saved old path is retrieved, and
   `CatalogTool.moveObject()` (injected by this add-on) is called.  It remaps
   `old_path → same RID → new_path` in the catalog's internal BTree structures,
   updates the modification date, then calls `reindexObject()` with **all
   indexes except the contextless ones** (see below).

The net result: the RID is preserved, and the contextless indexes
(`SearchableText` unless configured otherwise) are not recomputed.

For **renames** (same parent, new id) the same path is followed — the object
stays in the same container, only its path and id change.

For all other event types (add, copy, delete) the behaviour is identical to
stock CMFCore.

### Transaction-local path registry

The old path is stored via `transaction.set_data()` / `transaction.data()`,
keyed by a stable module-level singleton object.  This avoids the `_v_`
volatile attribute pattern, which is vulnerable to ZODB cache ghostification:
for large subtrees, objects can be evicted from the ZODB cache between the
`WillBeMoved` and `Moved` event phases, causing silent fallback to a full
reindex.  Transaction-attached data lives outside the ZODB object graph and is
discarded automatically on commit or abort.

### Contextless indexes

The catalog entry is remapped on move (RID preserved) instead of being
unindexed and indexed again.  Every index is then reindexed, except the
*contextless* ones: indexes whose value does not depend on the object's
location or security context.  They are listed in the optional
`contextless_indexes` lines property of `portal_catalog`.

**Without the property, `SearchableText` is treated as contextless**, where
most of the cost is.  This differs from upstream CMFCore#161, which reindexes
every index when the property is missing.  The property can be set from a
GenericSetup `catalog.xml`:

```xml
<object name="portal_catalog">
  <property name="contextless_indexes" type="lines">
    <element value="SearchableText" />
  </property>
</object>
```

Set the property to an empty list to opt out of the default and reindex every
index on move.  Add other indexes to the list only if their value cannot change
on move.

An index added later (e.g. through the ZMI) is reindexed on move unless it is
listed.  Do not list an index if a subscriber changes its value on move.

### Catalogs without `moveObject`

`moveObject(object, old_path)` is optional for `ICatalogTool` implementations.
If the registered catalog does not provide it (e.g. `plone-pgcatalog`), the
stock unindex + index flow is used.  `CatalogTool.moveObject` also updates the
modification date of the moved object, and returns `False` if nothing is
cataloged under `old_path` (the object is then indexed like a regular add).

Note for `IIndexQueueProcessor` implementations: a move now queues a
`reindex` at the new path instead of an `unindex` of the old path followed by
an `index`.

## Installation

Add `experimental.catalogmoveopt` to your Plone backend's dependencies:

```toml
# pyproject.toml
dependencies = [
    ...
    "experimental.catalogmoveopt",
]
```

The add-on uses `z3c.autoinclude.plugin` so its ZCML is loaded automatically
and the optimization is active as soon as the package is installed.

Note that this changes behavior without any further step: `SearchableText` is
no longer reindexed on move.  To keep reindexing it, set `contextless_indexes`
to an empty list (see above) or install the `uninstall` profile below.

No profile is required: when `portal_catalog` has no `contextless_indexes`
property, `SearchableText` is skipped on move.  Installing the
`experimental.catalogmoveopt:default` GenericSetup profile makes this explicit
by setting the property on `portal_catalog`, so it can be edited or exported.
The `experimental.catalogmoveopt:uninstall` profile sets it to an empty list,
so all indexes are reindexed on move.

## Compatibility

| Plone | Python |
|---|---|
| 6.0 | 3.10, 3.11 |
| 6.1 | 3.10, 3.11, 3.12 |
| 6.2 | 3.10, 3.11, 3.12, 3.13 |

## Development

```shell
git clone git@github.com:RedTurtle/experimental.catalogmoveopt.git
cd experimental.catalogmoveopt
make install
make test
```

## Prior art and upstream discussion

This add-on exists as a monkey-patch package while the optimization makes its
way into the Plone/CMFCore ecosystem proper.  Key references:

- **[4teamwork/ftw.copymovepatches](https://github.com/4teamwork/ftw.copymovepatches)**
  — the original proof-of-concept for Plone 4.3 that demonstrated the
  approach.  A real-world benchmark reported an 80-second move of a folder with
  ~300 files dropping to ~8 seconds (~10× speedup).

- **[plone/Products.CMFPlone#3834](https://github.com/plone/Products.CMFPlone/pull/3834#issuecomment-4091153715)**
  — David Glick's draft experiment bringing the same optimization to Plone 6,
  using `ftw.copymovepatches` as the starting point.  The linked comment
  explicitly requests that the fix land in CMFCore rather than as a
  monkey-patch in CMFPlone.

- **[zopefoundation/Products.CMFCore#161](https://github.com/zopefoundation/Products.CMFCore/pull/161)**
  — the upstream CMFCore pull request (by the author of this package) that
  proposes adding `CatalogTool.moveObject()` and the `contextless_indexes`
  catalog property directly to CMFCore.  Once merged, this add-on will become
  unnecessary.

## Contribute

- [Issue tracker](https://github.com/RedTurtle/experimental.catalogmoveopt/issues)
- [Source code](https://github.com/RedTurtle/experimental.catalogmoveopt/)

## License

The project is licensed under [GPLv2](LICENSE).
