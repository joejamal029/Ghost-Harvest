I completed the five-pass audit and produced both deliverables:

1. `SPRINT_FIX.md` with execution-ordered fixes, checkpoints, and known stubs
2. A ready-to-paste autonomous agent initiation prompt tailored to this codebase

The audit covers:

* platform/runtime blockers
* silent failure paths
* test integrity issues
* structural/environment flaws
* small high-leverage improvements

It also includes blindspot handling for:

* cross-platform subprocess flags
* background-thread GUI shutdown races
* destination collision corruption
* swallowed hash-worker exceptions
* RTL filename attacks
* PATH dependency failures for `robocopy`
