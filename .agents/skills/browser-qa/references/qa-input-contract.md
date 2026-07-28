# QA Input Contract

Before starting browser QA, collect or infer the smallest complete set of
inputs needed to reproduce the target flow.

## Required Inputs

- application URL or command to start the app;
- scenario name and user-visible goal;
- account type or role;
- setup data or fixture references;
- expected behavior;
- changed files, pull request, branch, or feature context when available;
- requested browsers, devices, or viewport sizes;
- artifacts requested by the user, such as screenshots, trace, or video.

## Missing Inputs

If a required input is missing:

- infer from repository docs when safe;
- use the lowest-risk local test account or fixture when documented;
- ask a concise question only when the scenario cannot be run safely;
- otherwise report the missing input as a QA blocker.

## Scope Control

Keep QA tied to the requested behavior. Add adjacent smoke checks only when the
changed surface makes them likely to fail, such as navigation around a touched
route or upload/download around a touched file picker.

## Start Conditions

Do not begin destructive or production-affecting browser actions unless the
environment is explicitly local, staging, seeded test data, or approved by the
user.
