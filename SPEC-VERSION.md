# Constitutional OS — Spec Version

## Current Version: v1.0.0

**Status:** FROZEN  
**Date:** March 2026  
**DOI:** 10.5281/zenodo.19075163

---

## What "frozen" means

Spec v1.0.0 is frozen. This means:

- The membrane semantics will not change
- The delta contract will not change
- The continuity chain format will not change
- The three integration hooks will not change
- The `constitution.yaml` schema will not change

Implementations built against spec v1.0.0 will continue to work
against any v1.x release.

---

## Version history

| Version | Status | Date | Notes |
|---------|--------|------|-------|
| v1.0.0 | **FROZEN** | March 2026 | Initial release |

---

## Version policy

### Patch versions (v1.0.x)
- Bug fixes to spec wording
- Clarifications that do not change semantics
- New examples and clarifying notes

### Minor versions (v1.x.0)
- New optional fields in `constitution.yaml`
- New event types in the continuity chain
- New built-in membrane or invariant types
- Backward-compatible extensions

### Major versions (vX.0.0)
- Changes to membrane semantics
- Changes to delta groupoid structure
- Changes to hash-linking rules
- Changes to the three integration hooks
- Any breaking change to existing implementations

Major version bumps require a migration guide and a 90-day
deprecation period for the prior version.

---

## Canonical reference

The mathematical foundations of spec v1.0.0 are archived at:

> *Constitutional OS: A Formal Governance Substrate for AI Systems*  
> Zetta Byte, Independent Researcher. Zenodo, March 2026.  
> DOI: [10.5281/zenodo.19075163](https://zenodo.org/records/19075163)

This DOI is immutable. It is the genesis block of the Constitutional OS standard.

---

## Declaring spec compliance

Implementations MUST declare which spec version they implement
in their `constitution.yaml`:

```yaml
constitutional_os_spec: "1.0"
```

And in their README:

```
Implements Constitutional OS Spec v1.0.0
DOI: 10.5281/zenodo.19075163
```
