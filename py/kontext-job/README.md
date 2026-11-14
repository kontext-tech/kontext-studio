# Kontext Jobs

Job framework and durable run orchestration for Kontext Python jobs.

## Overview

One package for the whole job lifecycle: the harness-neutral framework
(job classes, registry, execution, CRON scheduling) and the durable-run
orchestration services (`ExecutionRun` projection, status/event/log shaping,
run lifecycle helpers, worker coordination) that were previously in
`kontext-execution`.

## Components

- **Job Context**: execution context and service access for jobs
- **Job Result**: result models for job execution outcomes
- **Job Execution Service**: service layer for job orchestration
- **Job Definitions**: discovery namespace scanned by the registry for framework jobs
- **Job Registry**: discovery and instantiation of job types
- **Durable-Run Orchestration**: `ExecutionRunService`, status hooks, run
  projection, workflows, events/logs, polling (`job_run_dispatch`, `runs`,
  `workflows`, `events`, `polling`, ...)

Domain-specific jobs live in their owning packages (for example
`kontext-query`, `kontext-catalog`, and `kontext-file`);
the registry discovers them via `pkgutil` over a fixed set of packages.

## Usage

```python
from kontext.jobs import JobExecutionService
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
```

## Dependencies

- `kontext-auth`, `kontext-common`, `kontext-data`, `kontext-kernel`,
  `kontext-schema`
