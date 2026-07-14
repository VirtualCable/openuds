-- -*- coding: utf-8 -*-
--
-- DIAGNOSTIC ONLY. Lists the users duplicated by invisible characters
-- (BOM U+FEFF, ZWSP U+200B, ZWNJ U+200C, ZWJ U+200D, soft hyphen U+00AD, ...)
-- in the uds_user.name column.
--
-- This script does NOT modify anything. The actual cleanup (merging the
-- duplicates and keeping their groups, permissions, assigned services,
-- properties and logs) is done by the data migration
-- `uds/migrations/0048_dedupe_user_names.py`, which runs on upgrade.
-- Doing it by hand in SQL would silently drop the assigned user services of
-- the merged rows (FK CASCADE), so it is deliberately not offered here.
--
--   mysql ... < samples/uds_dedupe_users.sql
--
-- MySQL 8.0+ (CTE + REGEXP_REPLACE).
--
-- The invisible-char list below is only used to *report*, and covers what we
-- have seen in production. The migration does not need such a list: it uses the
-- Unicode category of every code point.

WITH cleaned AS (
    SELECT
        manager_id,
        TRIM(REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE(
            name,
            _utf8mb4'﻿', ''),    -- BOM      U+FEFF
            _utf8mb4'​', ''),    -- ZWSP     U+200B
            _utf8mb4'‌', ''),    -- ZWNJ     U+200C
            _utf8mb4'‍', ''),    -- ZWJ      U+200D
            _utf8mb4'­', '')     -- soft hyp U+00AD
        ) AS clean_name
    FROM uds_user
),
groups_ AS (
    SELECT manager_id, clean_name, COUNT(*) AS n
    FROM cleaned
    GROUP BY manager_id, clean_name
    HAVING COUNT(*) > 1
)
SELECT
    g.manager_id,
    a.name AS authenticator,
    g.clean_name,
    g.n AS duplicates
FROM groups_ g
JOIN uds_authenticator a ON a.id = g.manager_id
ORDER BY g.n DESC, a.name, g.clean_name;


-- ------------------------------------------------------------------------
-- PostgreSQL variant of the same query.
--   psql ... -f samples/uds_dedupe_users.sql
--
-- WITH cleaned AS (
--     SELECT
--         manager_id,
--         TRIM(
--             REGEXP_REPLACE(
--                 REGEXP_REPLACE(
--                     REGEXP_REPLACE(
--                         REGEXP_REPLACE(
--                             REGEXP_REPLACE(name, E'﻿', '', 'g'),
--                             E'​', '', 'g'),
--                         E'‌', '', 'g'),
--                     E'‍', '', 'g'),
--                 E'­', '', 'g')
--         ) AS clean_name
--     FROM uds_user
-- ),
-- groups_ AS (
--     SELECT manager_id, clean_name, COUNT(*) AS n
--     FROM cleaned GROUP BY manager_id, clean_name HAVING COUNT(*) > 1
-- )
-- SELECT g.manager_id, a.name AS authenticator, g.clean_name, g.n AS duplicates
-- FROM groups_ g JOIN uds_authenticator a ON a.id = g.manager_id
-- ORDER BY g.n DESC, a.name, g.clean_name;
