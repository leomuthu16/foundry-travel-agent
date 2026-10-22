---
id: release-2026-01
title: What's new in DataHub 2026.1
url: https://blog.contoso-datahub.example/release-2026-01
publish_date: 2026-01-15
author: Priya Raman
---
DataHub 2026.1 starts the year with scheduling improvements, a faster notebook runtime and a new connector.

## Pipelines
Pipeline schedules now accept cron expressions, so you can run a pipeline at 06:15 on weekdays or on the last day of each month. The maximum number of concurrent pipeline runs per workspace is raised from 10 to 20.

## Notebooks
Notebooks now run on a Python 3.11 runtime by default. Notebooks also save automatically every 30 seconds, so you no longer lose work when a browser tab closes.

## Connectors
A new Snowflake connector is available in preview. It supports reading tables and views and writing to existing tables.
