---
id: resilient-pipelines-retries
title: Designing resilient pipelines with automatic retries
url: https://blog.contoso-datahub.example/resilient-pipelines-retries
publish_date: 2026-04-02
author: Elena Petrova
---
Automatic retries, introduced in DataHub 2026.3, help pipelines recover from temporary failures. Used well, they reduce failed runs without hiding real problems.

## Make activities idempotent
A retried activity runs again from the start. Design activities so that running them twice gives the same result, for example by writing to a staging table and then swapping it in.

## Use increasing delays
Start with a short delay and increase it for each attempt. Temporary problems such as network timeouts or a busy source system often clear within a few minutes.

## Do not retry validation errors
Retries help with temporary failures only. A schema mismatch or a failed data-quality check will fail again on every attempt, so route those to an alert instead.
