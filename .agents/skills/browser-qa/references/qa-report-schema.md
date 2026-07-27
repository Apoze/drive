# QA Report Schema

Use concise reports that let a developer reproduce or accept the result.

## Passing Report

Include:

- environment and URL origin;
- browser or tool used;
- scenario steps covered;
- viewport sizes covered;
- console/network summary;
- screenshots or trace paths when created;
- final verdict.

## Defect Report

For each defect, include:

- title;
- severity: blocker, high, medium, low;
- reproduction steps;
- expected result;
- actual result;
- affected browser and viewport;
- console or network evidence, sanitized;
- screenshot or trace path when useful;
- likely ownership area if clear.

## Blocked Report

When QA cannot proceed, include:

- blocker reason;
- inputs missing or environment failure;
- actions already attempted;
- safest next step.

## Severity Guide

- `blocker`: core flow cannot be completed or data loss/security risk exists.
- `high`: major user-visible failure with no practical workaround.
- `medium`: important defect with a workaround or limited scope.
- `low`: polish issue, minor layout problem, or non-critical inconsistency.
