---
id: row-level-security-guide
title: Getting started with row-level security
url: https://blog.contoso-datahub.example/row-level-security-guide
publish_date: 2026-06-05
author: Daniel Okafor
---
Row-level security limits which rows of a dataset each user can see. This guide shows how to set it up.

## Define security roles
Open the dataset settings and create a role, for example "EMEA sales". Add a filter expression such as Region = "EMEA", then add users or groups to the role.

## Test with View as role
Use View as role to see the dataset exactly as a member of that role would. Always test each role before sharing the dataset.

## Keep filters simple
Filters on indexed columns perform best. Avoid filters that call functions on every row, because they slow down large datasets.
