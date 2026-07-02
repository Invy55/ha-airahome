# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Human-readable descriptions for heat pump alarms. The `..._alarms` binary
  sensor now exposes, for each active error, `error_N_code`, `error_N_severity`,
  `error_N_description`, and `error_N_suggested_action` (the last only when text
  is available), resolved from the error's `ccv`/`aira`/`power` code.

### Changed
- The alarm sensor's `error_N_code` attribute now reports the actual error-code
  name (e.g. `CCV_ERROR_CODE_ST_HP_OUT_AL_HIGH`) instead of the placeholder
  `"Unknown"` it previously always returned.

### Deprecated
- The `error_N_message` alarm-sensor attribute is **deprecated**. It is retained
  as an alias of `error_N_description` for backward compatibility and will be
  **removed in a future release**. Migrate automations, templates, and
  dashboards to `error_N_description`.

### Fixed
- The coordinator no longer mutates its cached last-successful state in place
  when reusing stale data (the scheduled hot water temperature was being written
  into the cache by reference).
- RSSI is now also fetched from the device when Home Assistant has no cached
  advertisement RSSI (previously this fallback ran only when that lookup raised),
  and it is skipped while disconnected to avoid a periodic ~5-second delay.
