# Security notes

## Safe local demo mode

The API binds to `127.0.0.1` by default. It does not implement authentication; do not bind it to a public or shared network. The application allows repository inspection and migration planning, but the migration-start endpoint returns HTTP 503 unless `ALLOW_UNSAFE_REPOSITORY_EXECUTION=true` is explicitly configured.

Enabling that setting is **not a security boundary**. Repository commands and package installers can execute arbitrary code with the backend process's filesystem and network permissions. A temporary copy, argument arrays, path validation, timeouts, and a restricted environment do not provide OS-level isolation, resource limits, or network isolation. Keep the setting disabled for untrusted repositories and public demos.

The temporary-copy helper rejects repositories containing symbolic links rather than following them into external files. Repository deletion removes only an unreferenced database registration; it does not delete the source directory or remote repository. Running migration jobs cannot currently be safely cancelled, so the API reports cancellation as unavailable rather than marking a still-running process as cancelled.

Git registration requires HTTPS, rejects embedded URL credentials and local hostnames, and rejects literal non-global IP addresses. Hostname resolution, DNS rebinding, clone time/size limits, and network egress restrictions are not enforced by this validation.

The service sends repository metadata to the configured model provider for planning. Failure diagnosis can also send selected source excerpts and command error output. Review the provider's data-handling terms and obtain approval before using proprietary code.

## Remaining safeguards needed before public deployment

- Add authentication and authorization to API endpoints.
- Run repository commands in a disposable OS/container/VM boundary with resource and network limits.
- Add cancellation and reliable process-tree termination.
- Add repository-clone and working-copy size/time limits.
- Review logs and reports for repository data and secret exposure.
- Add integration and security tests for the deployment boundary.
