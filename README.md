# charcoal-series
Source for new series of applications.

## Charcoal Browser filter lists

The weekly workflow downloads the sources in `filters/sources.json` every Monday at
03:23 UTC and can also be run manually. The Android app downloads the single
[filter bundle](https://github.com/Precision-Studios/charcoal-series/releases/latest/download/filters-v1.json.gz).
The bundle retains the publishers' attribution, notices, source URLs and individual
trust boundaries. uBlock Origin compiles the selected sources on the device.

Each version 1 source contains ordered UTF-8 text chunks and their combined SHA-256.
Duplicate-rule references let the publisher reconstruct each original source when
an upstream is unavailable. The build verifies those inputs against their original
checksums. Unchanged input produces no new release. To run the publisher checks,
use `python3 -m unittest discover -s filters`.
