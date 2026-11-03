# Kontext Jobs

Job execution framework for Kontext Python jobs.

## Overview

This package provides the job execution framework, context management, registry,
and core job definitions for Kontext's Python-based job execution system.

## Components

- **Job Context**: execution context and service access for jobs
- **Job Result**: result models for job execution outcomes
- **Job Execution Service**: service layer for job orchestration
- **Job Definitions**: discovery namespace scanned by the registry for framework jobs
- **Job Registry**: discovery and instantiation of job types

Domain-specific jobs live in their owning packages (for example
`kontext-execution`, `kontext-query`, `kontext-catalog`, and `kontext-file`);
the registry discovers them via `pkgutil` over a fixed set of packages.

## Usage

```python
from kontext.jobs import JobExecutionService
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
```

## Dependencies

- `kontext-auth`, `kontext-catalog`, `kontext-common`, `kontext-data`,
  `kontext-storage`
