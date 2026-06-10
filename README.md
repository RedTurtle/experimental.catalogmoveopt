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
   object's current physical path is saved in the transaction-local registry
   keyed by its ZODB `_p_oid`.  The catalog entry is left untouched.
2. **`IObjectMovedEvent`** — the saved old path is retrieved, and
   `CatalogTool.moveObject()` (injected by this add-on) is called.  It remaps
   `old_path → same RID → new_path` in the catalog's internal BTree structures,
   then calls `reindexObject()` with **only the context-aware indexes**.

The net result: the RID is preserved, only the path-dependent and
security-dependent indexes are recomputed, and the full reindex of expensive
text/metadata indexes is skipped entirely.

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

### Context-aware indexes

Only indexes whose values change when an object moves need to be reindexed.
This add-on ships with two built-in providers:

| Provider name | Indexes |
|---|---|
| `cmf.location` | `path`, `getId`, `id` |
| `cmf.security` | `allowedRolesAndUsers` |

Third-party packages can contribute additional indexes by registering a named
utility providing `IContextAwareIndexProvider`:

```xml
<!-- my.package/configure.zcml -->
<utility
    provides="experimental.catalogmoveopt.interfaces.IContextAwareIndexProvider"
    name="my.package.myindex"
    component=".providers.MyIndexProvider"
    />
```

```python
# my.package/providers.py
from zope.interface import implementer
from experimental.catalogmoveopt.interfaces import IContextAwareIndexProvider

@implementer(IContextAwareIndexProvider)
class MyIndexProvider:
    def getIndexNames(self):
        return ("my_custom_index",)
```

If no providers are registered the optimization is disabled and the stock
full-reindex path is used as a safe fallback.

## Installation

Add `experimental.catalogmoveopt` to your Plone backend's dependencies:

```toml
# pyproject.toml
dependencies = [
    ...
    "experimental.catalogmoveopt",
]
```

No further configuration is required.  The add-on uses
`z3c.autoinclude.plugin` so its ZCML is loaded automatically when installed in
a Plone site.

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
  proposes adding `CatalogTool.moveObject()` and the `IContextAwareIndexProvider`
  interface directly to CMFCore.  Once merged, this add-on will become
  unnecessary.

## Contribute

- [Issue tracker](https://github.com/RedTurtle/experimental.catalogmoveopt/issues)
- [Source code](https://github.com/RedTurtle/experimental.catalogmoveopt/)

## License

The project is licensed under [GPLv2](LICENSE).
