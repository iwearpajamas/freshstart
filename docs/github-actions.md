# Using Freshstart with GitHub Actions

The [Freshstart](../README.md) setup tester can be run from a repository's CI
to verify that every contributor's environment setup works.

## Example workflow

```yaml
name: Freshstart Setup Test

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test-setup:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run Freshstart
        uses: YOUR-ORG/freshstart@v1
        with:
          project-dir: '.'
          allow-network: 'true'
          report-dir: 'freshstart-reports'
```

## Action inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `project-dir` | no | `.` | Project directory to test (relative to the workspace root). |
| `config-path` | no | `.freshstart.yml` | Path to the configuration file, relative to the project directory. |
| `allow-network` | no | `false` | Allow network access inside the container. |
| `report-dir` | no | `freshstart-reports` | Directory for `freshstart-report.md` and `freshstart-report.json`. |

Reports are uploaded as a `freshstart-reports` artifact via
`actions/upload-artifact@v4` when files are found.

## Security notes

- The action uses minimal permissions (`contents: read`).
- Do not use `pull_request_target` for this action: it would execute setup
  commands defined in code from the PR.
- Project code is executed inside a disposable container with network
  disabled by default and resource limits applied. Projects should be treated
  as trusted for CI runs on forks.
- If you want reports as comments or artifacts, extend the workflow with
  `actions/upload-artifact@v4` or `mikefarah`-style steps; Freshstart only
  writes the report files.
