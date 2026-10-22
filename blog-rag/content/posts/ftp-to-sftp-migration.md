---
id: ftp-to-sftp-migration
title: Migrating from the legacy FTP connector to SFTP
url: https://blog.contoso-datahub.example/ftp-to-sftp-migration
publish_date: 2026-08-20
author: Marcus Webb
---
The legacy FTP connector was deprecated in DataHub 2026.7 and is planned for removal in 2026.11. This guide explains how to move to the SFTP connector.

## Find affected pipelines
Open the connections page and filter by connector type FTP. Each connection lists the pipelines that use it.

## Create the SFTP connection
Create a new SFTP connection with the same host. SFTP supports password and SSH key authentication; SSH keys are recommended.

## Switch and test
Change each pipeline to the new connection and run it once manually. Delete the FTP connection when all pipelines have been switched.
