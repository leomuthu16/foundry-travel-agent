---
id: faster-notebooks-tips
title: Five tips for faster notebooks
url: https://blog.contoso-datahub.example/faster-notebooks-tips
publish_date: 2026-09-24
author: Elena Petrova
---
Small changes can make DataHub notebooks noticeably faster.

## Cache data you reuse
If a notebook reads the same data in several cells, cache it once after loading instead of reading it again.

## Do not collect large data to the driver
Collecting a large table to the driver session is slow and can run out of memory. Aggregate or filter first.

## Pick the right session
Use the default CPU session for most work. GPU-backed sessions, in preview since 2026.9, help with machine learning training but cost more.

## Schedule from the editor
Since 2026.5 you can schedule a notebook directly from the editor, which avoids an extra pipeline for simple jobs.
