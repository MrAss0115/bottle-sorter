# Checks and validation boundaries

Run `python tests/run_host_checks.py --cxx <path-to-g++>` from the repository. A C++11 compiler is required. Output executables and JSON are written under ignored `build/host`.

The suites exercise the imported old-chute controller and manual-result demo using mocked Arduino time, serial and pins. There are 11 legacy cases and 12 manual-demo cases. They cover reference handling, pulse accounting, category routing, sequencing, hold/stop behaviour, timeout and command gating. They do not test a real motor, camera or sensor, or the new three-bin tray.

Historical Mega compilation passed before this import for both sketches. The public ESP32 change extracts the AP password to local_secrets.h; no ESP32 compilation is claimed. CAD exports, images and checks do not prove loaded mechanical operation. See ../docs/known-issues.md.
