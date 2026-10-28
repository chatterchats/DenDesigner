# Frozen service baseline

These are the adjacent ZComShare foundation source files used to review and test
the Community download extension. They are historical test data, not a second
service implementation. The Worker SHA-256 matches ../source.sha256. Files were
recovered by reversing the reviewed worker.patch from an isolated /tmp copy of
the amended service. The metadata, view and security modules were unchanged by
that patch. manifest.json records all source byte hashes.

Tests use this baseline rather than the live adjacent checkout, so applying or
deploying the extension does not invalidate the patch reproducibility test.
Do not edit the historical files to match future service changes; capture a new
versioned baseline when preparing another patch.
