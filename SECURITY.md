# Security

The Freshstart maintainers take security seriously. Please do not report
vulnerabilities through public channels; use
[GitHub's private vulnerability reporting](https://github.com/your-org/freshstart/security/advisories/new)
instead.

When reporting, please include:

- The affected commands and code paths.
- Steps to reproduce.
- A description of the impact.
- Any suggested mitigations.

Note: Freshstart executes project setup code inside disposable Docker
containers; the threat model covers the tool itself, and the
[docs/docker-security.md](docs/docker-security.md) page describes the
assumptions the tool makes.
