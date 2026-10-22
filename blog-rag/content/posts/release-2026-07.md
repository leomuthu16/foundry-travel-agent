---
id: release-2026-07
title: What's new in DataHub 2026.7
url: https://blog.contoso-datahub.example/release-2026-07
publish_date: 2026-07-16
author: Priya Raman
---
DataHub 2026.7 adds pipeline versioning and makes row-level security generally available.

## Pipelines
Every saved change to a pipeline now creates a version. You can compare any two versions side by side and roll back to any of the last 20 versions.

## Security
Row-level security is now generally available. Workspaces can also use customer-managed keys to encrypt stored data.

## Deprecation notice
The legacy FTP connector is deprecated. It will be removed in DataHub 2026.11. Move existing connections to the SFTP connector before then.
