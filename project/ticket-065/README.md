# Ticket 065: Reject invalid strategy input

Status: IN_PROGRESS / EDIT

Issue: https://github.com/semcod/planfile/issues/65
Doctor evidence: subactor/doctor-agent#381 (PLF-13741) and #382 (PLF-13742).
SESSION_EXECUTION_AUTHORIZATION: repair, test, push and protected merge, continued on 2026-09-10.

Scope: reject unreadable, malformed or non-mapping strategy input in validation and TODO synchronization. Valid mappings retain current behavior. Failed loading must not report empty success or write TODO based on result markers. No changes to queue authority or automatic diagnostic closure.

Acceptance: regression tests demonstrate explicit load failures, unchanged TODO bytes, safe error messages, and existing valid-input behavior.
