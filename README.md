# charcoal-series
Source for new series of applications.

## Charcoal Browser releases

- **Filter updates.** Charcoal downloads the exact [`filters-v1.json.gz`](https://github.com/Precision-Studios/charcoal-series/releases/latest/download/filters-v1.json.gz) asset from the release marked **Latest**. If an update fails, it keeps the last working filters or uses the bundled starter list.
- **Blocker source.** Download the named ZIP from the [versioned uBlock Origin source release](https://github.com/Precision-Studios/charcoal-series/releases/tag/charcoal-browser-source-1). It contains pinned upstream sources, Charcoal’s blocker modifications, the dedicated Android integration (`TrackerBridge.kt`, `FilterListStore.kt`, and `FilterCatalog.kt`), and build instructions. The ZIP covers the blocker component. Source releases have their own tags, and **Latest** is reserved for filter bundles.
- **Licenses.** The filter publisher code and workflow use [Apache-2.0](LICENSE). The modified uBlock Origin component and Charcoal’s blocker code in the source ZIP use [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html). Filter lists retain their upstream licenses and attribution as described in [NOTICE](NOTICE).
