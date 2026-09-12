# Changelog

## 1.0.7

- Allow insecure HTTPS for API servers with invalid certificates.

## 1.0.6

- Detect Ollama from macOS app launches that do not inherit Terminal PATH.
- Add Dashboard setup repair progress and command output for Chromium/model downloads.
- Open Dashboard on first launch and run setup there so progress is visible immediately.
- Fix packaged default config so fresh installs do not skip first-launch setup.

## 1.0.5

- Prevent startup crash when GitHub update checks fail because of certificate or network errors.

## 1.0.4

- Fix macOS bundle version metadata so Finder and LaunchServices see the correct app version.

## 1.0.3

- Show missing setup components directly on Dashboard.
- Show LinkPilot, Ollama, browser, and Playwright-related processes running on the machine.

## 1.0.2

- Enable GitHub release update checks by default.
- Migrate older blank update URLs to the official LinkPilot release feed.

## 1.0.1

- Show first-launch setup progress while Chromium and Ollama models download.
- Fix packaged Playwright Chromium install command.
- Fix Setup page Ollama installer link on fresh systems.

## 1.0.0 RC1

- Native macOS and Windows packaging scripts.
- Secure credential storage.
- Hybrid DOM and vision browser agent.
- Telemetry, updater staging, diagnostics, benchmarks, release checklist.
- Crash reports and log rotation.
