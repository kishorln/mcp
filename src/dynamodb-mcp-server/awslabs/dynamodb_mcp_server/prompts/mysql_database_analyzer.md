# MySQL Database Analysis for DynamoDB Migration

🚨 **CRITICAL: ALL SQL QUERIES MUST USE THE EXACT TEMPLATES BELOW**
🚨 **DO NOT CREATE CUSTOM SQL - FIND THE TEMPLATE AND COPY IT**
🚨 **TEMPLATES ARE PROVIDED IN EACH STEP - USE THEM EXACTLY**

## 🔴 MANDATORY SQL TEMPLATES - USE THESE EXACTLY

### TEMPLATE 1 - DATABASE IDENTIFICATION
```sql
SELECT DATABASE() as configured_database;
```

### TEMPLATE 2 - GENERAL LOG CHECK
```sql
SELECT 
  @@global.general_log as general_log_enabled,
  @@global.log_output as log_output_setting,
  @@global.general_log_file as log_file_path,
  CASE 
    WHEN @@global.general_log = 1 AND @@global.log_output LIKE '%TABLE%' THEN 'READY: General log enabled with TABLE output'
    WHEN @@global.general_log = 1 AND @@global.log_output = 'FILE' THEN 'WARNING: General log enabled but using FILE output (need TABLE for analysis)'
    WHEN @@global.general_log = 0 THEN 'ERROR: General log is disabled'
    ELSE 'ERROR: General log configuration issue'
  END as status;
```

### TEMPLATE 3 - USER ACTIVITY CHECK
```sql
SELECT 
  user_host, 
  COUNT(*) as total_queries,
  COUNT(DISTINCT CONVERT(argument USING utf8)) as unique_patterns,
  ROUND(COUNT(DISTINCT CONVERT(argument USING utf8)) / COUNT(*) * 100, 2) as pattern_diversity_pct
FROM mysql.general_log 
WHERE command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND user_host NOT LIKE '%rdsadmin%'
  AND user_host NOT LIKE '%system%'
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use %'
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND EXISTS (
    SELECT 1 FROM information_schema.TABLES t 
    WHERE t.TABLE_SCHEMA = [CONFIGURED_DATABASE] 
    AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
  )
GROUP BY user_host 
HAVING total_queries >= 25 AND unique_patterns >= 10
ORDER BY unique_patterns DESC, total_queries DESC
LIMIT 20;
```

### TEMPLATE 4 - DATABASE ACTIVITY VALIDATION (FALLBACK)
```sql
SELECT 
  TABLE_SCHEMA as database_name,
  COUNT(*) as table_count,
  CASE 
    WHEN COUNT(*) <= 5 THEN 50
    WHEN COUNT(*) <= 20 THEN 100
    ELSE 200
  END as min_queries_needed,
  CASE 
    WHEN COUNT(*) <= 5 THEN 10
    WHEN COUNT(*) <= 20 THEN 25
    ELSE 50
  END as min_patterns_needed
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
GROUP BY TABLE_SCHEMA
HAVING COUNT(*) > 0
ORDER BY table_count DESC
LIMIT 10;
```

### TEMPLATE 5 - STEP 1 PATTERN ANALYSIS (24h)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type
FROM mysql.general_log 
WHERE [USER_FILTER_PLACEHOLDER] 
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%CONVERT(argument USING utf8)%'
  AND CONVERT(argument USING utf8) NOT LIKE '%query_pattern%'
  AND CONVERT(argument USING utf8) NOT LIKE '%frequency%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 6 - CROSS-DATABASE COUNT
```sql
SELECT 
  COUNT(CASE WHEN query_type = 'cross_db' THEN 1 END) as cross_db_count,
  COUNT(CASE WHEN query_type = 'primary_db' THEN 1 END) as primary_db_count
FROM ([STEP_1_RESULTS]);
```

### TEMPLATE 7 - PATTERN VALIDATION  
```sql
SELECT 
  COUNT(*) as meaningful_patterns,
  COUNT(CASE WHEN query_type = 'cross_db' THEN 1 END) as cross_db_patterns
FROM ([STEP_1_RESULTS]) 
WHERE query_pattern NOT LIKE '%mysql.general_log%'
  AND query_pattern NOT LIKE 'SHOW %'
  AND query_pattern NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND query_pattern NOT LIKE 'SELECT @@%'
  AND query_pattern NOT LIKE 'DESCRIBE %'
  AND query_pattern NOT LIKE 'SET %'
  AND EXISTS (
    SELECT 1 FROM information_schema.TABLES t 
    WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]' 
    AND query_pattern REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
  );
```

### TEMPLATE 8 - SCHEMA ANALYSIS
```sql
SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = '[CONFIGURED_DATABASE]';

SELECT 
  COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, 
  COLUMN_KEY, COLUMN_DEFAULT, EXTRA
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = '[CONFIGURED_DATABASE]' 
ORDER BY TABLE_NAME, ORDINAL_POSITION;

SELECT 
  TABLE_NAME, INDEX_NAME, COLUMN_NAME, 
  NON_UNIQUE, SEQ_IN_INDEX
FROM information_schema.STATISTICS 
WHERE TABLE_SCHEMA = '[CONFIGURED_DATABASE]';

SELECT 
  CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME,
  REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE 
WHERE TABLE_SCHEMA = '[CONFIGURED_DATABASE]' 
  AND REFERENCED_TABLE_NAME IS NOT NULL;
```

### TEMPLATE 9 - TRAFFIC ANALYSIS
```sql
-- Replace [ANALYSIS_PERIOD_DAYS] with actual days from successful step:
-- Step 1: 1, Step 2: 7, Step 3: 30, Step 4: 365, Step 5: 1, Step 6: 30
-- Replace [USER_FILTER_CONDITION] with appropriate user filter or "user_host NOT LIKE 'rdsadmin%'" for all users
-- Replace [INCLUDE_CROSS_DB] with TRUE or FALSE based on user consent

SELECT 
  DATE(event_time) as analysis_date,
  HOUR(event_time) as analysis_hour,
  COUNT(*) as total_queries,
  COUNT(*) / 3600 as avg_rps_this_hour,
  COUNT(DISTINCT user_host) as unique_users,
  -- Categorize by query type
  COUNT(CASE WHEN argument LIKE '%[CONFIGURED_DATABASE].%' THEN 1 END) as primary_db_queries,
  COUNT(CASE WHEN argument REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*' 
              AND argument NOT LIKE '%[CONFIGURED_DATABASE].%' THEN 1 END) as cross_db_queries
FROM mysql.general_log 
WHERE event_time >= DATE_SUB(NOW(), INTERVAL [ANALYSIS_PERIOD_DAYS] DAY)
  AND command_type = 'Query'
  -- Apply same filters as pattern analysis
  AND argument NOT LIKE 'SET %'
  AND argument NOT LIKE 'SHOW %'
  AND argument NOT LIKE 'SELECT @@%'
  AND argument NOT LIKE 'SELECT 1'
  AND argument NOT LIKE '%mysql.general_log%'
  AND argument NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  -- Include based on user consent for cross-database
  AND (
    -- Always include primary database queries
    argument LIKE '%[CONFIGURED_DATABASE].%' 
    OR argument LIKE 'USE [CONFIGURED_DATABASE]%'
    OR (
      argument NOT LIKE '%.%' 
      AND argument NOT LIKE 'USE %'
      AND EXISTS (
        SELECT 1 FROM information_schema.TABLES t 
        WHERE t.TABLE_SCHEMA = [CONFIGURED_DATABASE] 
        AND argument REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
      )
    )
    -- Include cross-database queries only if user consented
    OR (
      @include_cross_db = TRUE
      AND argument REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
      AND argument NOT LIKE CONCAT('%', [CONFIGURED_DATABASE], '.%')
      AND REGEXP_SUBSTR(argument, '[a-zA-Z_][a-zA-Z0-9_]*(?=\\.)') NOT IN (
        'information_schema', 'performance_schema', 'mysql', 'sys'
      )
    )
  )
GROUP BY DATE(event_time), HOUR(event_time)
ORDER BY analysis_date DESC, analysis_hour DESC;

-- Calculate overall RPS for the analysis period
SELECT 
  COUNT(*) as total_queries_in_period,
  COUNT(*) / ([ANALYSIS_PERIOD_DAYS] * 24 * 3600) as average_rps,
  MAX(hourly_queries) as peak_hourly_queries,
  MAX(hourly_queries) / 3600 as peak_rps,
  @analysis_period_days as analysis_period_days,
  CASE @successful_step
    WHEN 1 THEN '24 hours (selected users)'
    WHEN 2 THEN '7 days (selected users)'  
    WHEN 3 THEN '30 days (selected users)'
    WHEN 4 THEN '1 year (selected users)'
    WHEN 5 THEN '24 hours (all users)'
    WHEN 6 THEN '30 days (all users)'
  END as analysis_period_description
FROM (
  SELECT DATE(event_time), HOUR(event_time), COUNT(*) as hourly_queries
  FROM mysql.general_log 
  WHERE event_time >= DATE_SUB(NOW(), INTERVAL @analysis_period_days DAY)
    AND command_type = 'Query'
    -- CRITICAL: Use EXACT same filters as pattern analysis
    AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
    AND (
      -- Apply user type filter based on successful step
      CASE @successful_step
        WHEN 1,2,3,4 THEN [USER_FILTER_PLACEHOLDER]           -- user choice steps
        WHEN 5,6 THEN user_host NOT LIKE "rdsadmin%"        -- All users steps
      END
    )
    AND argument NOT LIKE 'SET %'
    AND argument NOT LIKE 'SHOW %'
    AND argument NOT LIKE 'SELECT @@%'
    AND argument NOT LIKE 'SELECT 1'
    AND argument NOT LIKE '%mysql.general_log%'
    AND argument NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
    AND argument NOT LIKE '%frequency%RPS%'
    -- CRITICAL: Use EXACT same table filtering as pattern analysis
    AND (
      -- Always include primary database queries
      argument LIKE CONCAT('%', [CONFIGURED_DATABASE], '.%') 
      OR argument LIKE CONCAT('USE ', [CONFIGURED_DATABASE], '%')
      OR (
        argument NOT LIKE '%.%' 
        AND argument NOT LIKE 'USE %'
        AND EXISTS (
          SELECT 1 FROM information_schema.TABLES t 
          WHERE t.TABLE_SCHEMA = [CONFIGURED_DATABASE] 
          AND argument REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
        )
        -- Check if it ALSO references non-configured tables (JOIN scenario)
        AND NOT EXISTS (
          SELECT 1 FROM information_schema.TABLES t2
          WHERE t2.TABLE_SCHEMA != [CONFIGURED_DATABASE]
          AND t2.TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
          AND argument REGEXP CONCAT('\\b', t2.TABLE_NAME, '\\b')
        )
      )
      -- Include cross-database queries only if user consented
      OR (
        @include_cross_db = TRUE
        AND (
          -- Explicit cross-database references
          (argument REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
           AND argument NOT LIKE CONCAT('%', [CONFIGURED_DATABASE], '.%')
           AND REGEXP_SUBSTR(argument, '[a-zA-Z_][a-zA-Z0-9_]*(?=\\.)') NOT IN (
             'information_schema', 'performance_schema', 'mysql', 'sys'
           ))
          -- Implicit cross-database joins
          OR (argument NOT LIKE '%.%' 
              AND argument NOT LIKE 'USE %'
              AND EXISTS (
                SELECT 1 FROM information_schema.TABLES t 
                WHERE t.TABLE_SCHEMA = [CONFIGURED_DATABASE] 
                AND argument REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
              )
              AND EXISTS (
                SELECT 1 FROM information_schema.TABLES t2
                WHERE t2.TABLE_SCHEMA != [CONFIGURED_DATABASE]
                AND t2.TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                AND argument REGEXP CONCAT('\\b', t2.TABLE_NAME, '\\b')
              ))
        )
      )
    )
  GROUP BY DATE(event_time), HOUR(event_time)
) hourly_stats;
```

### TEMPLATE 10 - STEP 2 PATTERN ANALYSIS (7d)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type
FROM mysql.general_log 
WHERE [USER_FILTER_PLACEHOLDER] 
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%CONVERT(argument USING utf8)%'
  AND CONVERT(argument USING utf8) NOT LIKE '%query_pattern%'
  AND CONVERT(argument USING utf8) NOT LIKE '%frequency%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 11 - STEP 3 PATTERN ANALYSIS (30d)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type
FROM mysql.general_log 
WHERE [USER_FILTER_PLACEHOLDER] 
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%CONVERT(argument USING utf8)%'
  AND CONVERT(argument USING utf8) NOT LIKE '%query_pattern%'
  AND CONVERT(argument USING utf8) NOT LIKE '%frequency%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 12 - STEP 4 PATTERN ANALYSIS (365d)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type
FROM mysql.general_log 
WHERE [USER_FILTER_PLACEHOLDER] 
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 365 DAY)
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%CONVERT(argument USING utf8)%'
  AND CONVERT(argument USING utf8) NOT LIKE '%query_pattern%'
  AND CONVERT(argument USING utf8) NOT LIKE '%frequency%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 13 - STEP 5 PATTERN ANALYSIS (24h ALL USERS)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type
FROM mysql.general_log 
WHERE command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
  AND user_host NOT LIKE '%rdsadmin%'
  AND user_host NOT LIKE '%system%'
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%CONVERT(argument USING utf8)%'
  AND CONVERT(argument USING utf8) NOT LIKE '%query_pattern%'
  AND CONVERT(argument USING utf8) NOT LIKE '%frequency%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
  AND (
    CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' 
    OR CONVERT(argument USING utf8) LIKE 'USE [CONFIGURED_DATABASE]%'
    OR (
      CONVERT(argument USING utf8) NOT LIKE '%.%' 
      AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
      AND EXISTS (
        SELECT 1 FROM information_schema.TABLES t 
        WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]' 
        AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
      )
    )
  )
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 14 - STEP 6 PATTERN ANALYSIS (30d ALL USERS)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type
FROM mysql.general_log 
WHERE command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND user_host NOT LIKE '%rdsadmin%'
  AND user_host NOT LIKE '%system%'
  AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%CONVERT(argument USING utf8)%'
  AND CONVERT(argument USING utf8) NOT LIKE '%query_pattern%'
  AND CONVERT(argument USING utf8) NOT LIKE '%frequency%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [CONFIGURED_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
  AND (
    CONVERT(argument USING utf8) LIKE '%[CONFIGURED_DATABASE].%' 
    OR CONVERT(argument USING utf8) LIKE 'USE [CONFIGURED_DATABASE]%'
    OR (
      CONVERT(argument USING utf8) NOT LIKE '%.%' 
      AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
      AND EXISTS (
        SELECT 1 FROM information_schema.TABLES t 
        WHERE t.TABLE_SCHEMA = '[CONFIGURED_DATABASE]'
        AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
      )
    )
    OR (
      CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
      AND EXISTS (
        SELECT 1 FROM information_schema.SCHEMATA s
        WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
        AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
        AND s.SCHEMA_NAME != '[CONFIGURED_DATABASE]'
      )
    )
  )
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 15 - MYSQL REQUIREMENTS FILE
```markdown
# MySQL Database Analysis Results

## Analysis Metadata
- **Analysis Date**: [CURRENT_TIMESTAMP]
- **Source Database**: [CONFIGURED_DATABASE]
- **Analysis Period**: [ANALYSIS_PERIOD_DESCRIPTION]
- **Cross-Database Included**: [TRUE/FALSE_BASED_ON_USER_CONSENT]
- **Total Patterns Found**: [MEANINGFUL_PATTERN_COUNT]
- **Analysis Step**: [SUCCESSFUL_STEP_NUMBER]

## Database Schema Summary

### Tables Analyzed
| Table | Rows | Data Size | Index Size | Primary Key | Foreign Keys |
|-------|------|-----------|------------|-------------|--------------|
[TABLE_ANALYSIS_RESULTS]

### Relationships Detected
[FOREIGN_KEY_RELATIONSHIPS]

## Access Patterns Discovered

### Pattern Summary
| Pattern # | Original MySQL Query | Frequency | RPS | Type | Tables Accessed |
|-----------|---------------------|-----------|-----|------|-----------------|
[PATTERN_ANALYSIS_RESULTS]

### High Frequency Patterns (>1.0 RPS)
[HIGH_FREQUENCY_PATTERNS]

### Medium Frequency Patterns (0.01-1.0 RPS)
[MEDIUM_FREQUENCY_PATTERNS]

### Low Frequency Patterns (<0.01 RPS)
[LOW_FREQUENCY_PATTERNS]

## Traffic Analysis

### Overall Statistics
- **Total RPS**: [CALCULATED_TOTAL_RPS]
- **Peak Hour**: [PEAK_HOUR_ANALYSIS]
- **Read/Write Ratio**: [READ_WRITE_RATIO]
- **Unique Users**: [UNIQUE_USER_COUNT]
- **Analysis Period**: [ACTUAL_TIME_PERIOD]

### Data Volume
[TABLE_DATA_VOLUMES]

## Cross-Database Analysis
[IF_CROSS_DB_INCLUDED]
### Multi-Database Patterns Found
[CROSS_DATABASE_PATTERNS]

[IF_CROSS_DB_EXCLUDED]
Cross-database analysis excluded by user choice. Analysis focused on: [CONFIGURED_DATABASE]

## Technical Notes

### Analysis Quality
- **Query Log Coverage**: [LOG_COVERAGE_ASSESSMENT]
- **Pattern Detection Method**: Automated from mysql.general_log
- **RPS Calculation**: Query frequency divided by analysis period seconds
- **Schema Source**: information_schema tables
- **Confidence Level**: [HIGH/MEDIUM/LOW]

### Limitations
- **Sample Period**: [ACTUAL_ANALYSIS_PERIOD]
- **Missing Patterns**: [POTENTIAL_GAPS]
- **System Queries**: Excluded from analysis

---
*Generated by MySQL Database Analyzer*
*Ready for DynamoDB Data Modeling Tool*

## Next Steps
1. Review patterns for accuracy and business context
2. Use `dynamodb_data_modeling` tool with this analysis
3. The modeling tool will use this MySQL analysis as input and gather additional requirements if needed
```

## WORKFLOW

### Step 0: Database Identification
1. Execute TEMPLATE 1 - DATABASE IDENTIFICATION
   - If this fails: Provide MySQL MCP configuration instructions below, then STOP

2. Execute TEMPLATE 2 - GENERAL LOG CHECK
   - If general_log is disabled: STOP and provide configuration instructions
   - If log_output is not TABLE: STOP and provide configuration instructions  
   - If mysql.general_log table is not accessible: STOP and provide configuration instructions

**CRITICAL**: Do NOT proceed with analysis if MySQL general log is not properly configured for TABLE output.
   - If successful: Continue with remaining steps
2. Execute TEMPLATE 2 - GENERAL LOG CHECK  
3. Execute TEMPLATE 3 - USER ACTIVITY CHECK (replace [CONFIGURED_DATABASE])
4. If no users found: Execute TEMPLATE 4 - DATABASE ACTIVITY VALIDATION

**AI Response Template for TEMPLATE 2:**
```
🤖 AI: "Checking MySQL general_log status...

Database: [DATABASE_NAME]
General Log: [ENABLED/DISABLED]
Log Output: [TABLE/FILE/NONE]
Log Entries (24h): [COUNT]
Unique Users: [COUNT]
Unique Queries: [COUNT]

[IF DISABLED OR FILE OUTPUT]: ❌ General log needs configuration for RDS MySQL:

📋 RDS MySQL General Log Setup:
1. Open Amazon RDS console → Parameter groups
2. Select your custom parameter group (create one if needed)
3. Set these parameters:
   - general_log = 1
   - log_output = TABLE (required for analysis)
   - slow_query_log = 1 (optional)
   - long_query_time = 2 (optional)
4. Associate parameter group with your DB instance
5. No reboot required (dynamic parameters)

Wait 5-10 minutes for logs to populate, then retry analysis.

[IF ENABLED]: ✅ General log is ready for analysis.
```

**CRITICAL**: If general_log is disabled, log_output is not TABLE, or no recent data exists, STOP analysis and provide RDS configuration instructions.

**AI Response Template for TEMPLATE 3:**
```
🤖 AI: "I can see your mysql-mcp-server is configured for database: [DATABASE_NAME]

Database Analysis ([X] tables = [small/medium/large] database):
- Required minimum: [X] queries, [X] patterns per user
- Pattern threshold: [X] meaningful patterns needed

Available users with sufficient activity:
[LIST OF user_host VALUES WITH total_queries, unique_patterns, pattern_diversity_pct]

[IF USERS FOUND]:
Which user_host patterns would you like me to analyze? You can:
- Select specific users (e.g., 'app_user%', 'web_user%')  
- Choose 'top' to analyze the highest diversity user
- Choose 'top3' to analyze top 3 users combined
- Choose 'all' to analyze for all users patterns
- Provide a custom LIKE pattern

[IF NO USERS FOUND]:
❌ No users found with sufficient activity on database '[DATABASE_NAME]'.

Alternative databases with active users:
[LIST OF database_name WITH table_count, min_queries_needed, min_patterns_needed]

Would you like to:
1. Analyze a different database (specify database name) (if yes, skip to Step 6 - 30d all users analysis only)
2. Lower the activity threshold for current database (if yes, skip to Step 6 - 30d all users analysis only)
3. Switch to manual DynamoDB modeling approach

Please specify your choice."
```

**CRITICAL**: Wait for user selection before proceeding to Step 1. If switching databases, update [CONFIGURED_DATABASE] for all subsequent queries.

**IMPORTANT**: In all subsequent queries, replace `[CONFIGURED_DATABASE]` with the actual database name from Step 0.

## User Filter Construction

After user selection in Step 0, construct the appropriate WHERE clause:

**Single user pattern:**
```sql
WHERE user_host LIKE 'selected_pattern%'
```

**Multiple user patterns:**
```sql
WHERE (user_host LIKE 'pattern1%' OR user_host LIKE 'pattern2%' OR user_host LIKE 'pattern3%')
```

**All non-system users:**
```sql
WHERE user_host NOT LIKE '%rdsadmin%' 
  AND user_host NOT LIKE '%system%'
  AND user_host IS NOT NULL
```

Replace `[USER_FILTER_PLACEHOLDER]` in all subsequent queries with the constructed filter.

## Cross-Database Detection and User Consent

**After Step 1 - Check Results for Cross-Database Queries:**

Execute TEMPLATE 6 - CROSS-DATABASE COUNT using Step 1 results

**User Consent Logic:**
```
IF cross_db_count > 0:
  Show user consent template below
ELSE:
  Skip cross-database consent (no business databases detected)
  Continue with primary database analysis only
```

**User Consent Template (only when cross_db_count > 0):**
```
🔴 BUSINESS CROSS-DATABASE QUERIES DETECTED:

🔗 Cross-Database Queries Found: [cross_db_count] patterns

For DynamoDB migration analysis, I can:
1. **Focus only on [DATABASE_NAME]** (single-service migration)
2. **Include cross-database patterns** (multi-service migration)

Which approach would you prefer? [WAIT FOR USER RESPONSE]
```

## Enhanced Pattern Validation

**Mandatory Validation After Each Step:**

Execute TEMPLATE 7 - PATTERN VALIDATION using previous step results

**Stop Condition Logic:**
```
🔴 MANDATORY VALIDATION SEQUENCE:

1. Execute step query
2. Detect cross-database queries  
3. IF cross-database found AND no user consent yet: ASK USER
4. Count meaningful patterns (with user consent applied)
5. Calculate threshold: @pattern_threshold = CASE 
     WHEN table_count ≤ 5 THEN 10
     WHEN table_count ≤ 20 THEN 25  
     ELSE 50 END
6. IF meaningful_patterns >= @pattern_threshold: Proceed to Schema and Traffic Analysis
7. IF current_step < 5: PROCEED to next step
8. IF current_step = 5: ALWAYS proceed to Schema and Traffic Analysis
```

**MySQL MCP Configuration (show only if TEMPLATE 1 fails):**

🔧 Add this to your ~/.aws/amazonq/mcp.json:

```json
{
  "mcpServers": {
    "awslabs.mysql-mcp-server": {
      "command": "uvx",
      "args": [
        "awslabs.mysql-mcp-server@latest",
        "--resource_arn", "[your RDS resource ARN]",
        "--secret_arn", "[your secrets manager ARN]",
        "--database", "[your database name]",
        "--region", "[your AWS region]",
        "--readonly", "True"
      ],
      "env": {
        "AWS_PROFILE": "your-aws-profile",
        "AWS_REGION": "us-east-1",
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

📖 Documentation: https://github.com/awslabs/mcp/blob/main/src/mysql-mcp-server/README.md

Restart Q CLI after configuration, then retry analysis.

### Step 1: Pattern Analysis (24h)
1. Execute TEMPLATE 5 - STEP 1 PATTERN ANALYSIS (replace [CONFIGURED_DATABASE] and [USER_FILTER_PLACEHOLDER])
2. Execute TEMPLATE 6 - CROSS-DATABASE COUNT (use Step 1 results)
3. If cross_db_count > 0: Ask user consent for cross-database inclusion
4. Execute TEMPLATE 7 - PATTERN VALIDATION (use Step 1 results)
5. If meaningful_patterns >= threshold: Proceed to Schema and Traffic Analysis
6. If meaningful_patterns < threshold: Proceed to Step 2

### Step 2: Pattern Analysis (7d)
1. Execute TEMPLATE 10 - STEP 2 PATTERN ANALYSIS (replace [CONFIGURED_DATABASE] and [USER_FILTER_PLACEHOLDER])
2. Execute TEMPLATE 7 - PATTERN VALIDATION (use Step 2 results)
3. If meaningful_patterns >= threshold: Proceed to Schema and Traffic Analysis
4. If meaningful_patterns < threshold: Proceed to Step 3

### Step 3: Pattern Analysis (30d)
1. Execute TEMPLATE 11 - STEP 3 PATTERN ANALYSIS (replace [CONFIGURED_DATABASE] and [USER_FILTER_PLACEHOLDER])
2. Execute TEMPLATE 7 - PATTERN VALIDATION (use Step 3 results)
3. If meaningful_patterns >= threshold: Proceed to Schema and Traffic Analysis
4. If meaningful_patterns < threshold: Proceed to Step 4

### Step 4: Pattern Analysis (365d)
1. Execute TEMPLATE 12 - STEP 4 PATTERN ANALYSIS (replace [CONFIGURED_DATABASE] and [USER_FILTER_PLACEHOLDER])
2. Execute TEMPLATE 7 - PATTERN VALIDATION (use Step 4 results)
3. If meaningful_patterns >= threshold: Proceed to Schema and Traffic Analysis
4. If meaningful_patterns < threshold: Proceed to Step 5

### Step 5: Pattern Analysis (All Users for 24hrs)
**SKIP CONDITIONS**: If user already consented to "all users" in Steps 1-4, skip Step 5 and proceed directly to Schema and Traffic Analysis.

1. Execute TEMPLATE 13 - STEP 5 PATTERN ANALYSIS (replace [CONFIGURED_DATABASE])
2. Execute TEMPLATE 7 - PATTERN VALIDATION (use Step 5 results)
3. Proceed to Schema and Traffic Analysis (regardless of pattern count)
3. Proceed to Schema and Traffic Analysis (regardless of pattern count)

### Step 6: Pattern Analysis (All Users for 30 days)
**SKIP CONDITIONS**: If user already consented to "all users" in Steps 1-4, skip Step 5 and proceed directly to Schema and Traffic Analysis.

1. Execute TEMPLATE 14 - STEP 6 PATTERN ANALYSIS (replace [CONFIGURED_DATABASE])
2. Execute TEMPLATE 7 - PATTERN VALIDATION (use Step 5 results)
3. Proceed to Schema and Traffic Analysis (regardless of pattern count)
3. Proceed to Schema and Traffic Analysis (regardless of pattern count)

### Schema and Traffic Analysis
1. Execute TEMPLATE 8 - SCHEMA ANALYSIS (replace [CONFIGURED_DATABASE])
2. Execute TEMPLATE 9 - TRAFFIC ANALYSIS (replace placeholders based on successful step)

### Final Output
**MANDATORY**: ALWAYS create mysql_requirements.md file regardless of analysis success/failure
1. Use TEMPLATE 15 - MYSQL REQUIREMENTS FILE to create mysql_requirements.md
2. Replace all placeholders with actual analysis results from pattern, schema, and traffic analysis
3. If analysis failed or insufficient data: Mark sections as "Insufficient data" but still create the file
4. Provide completed mysql_requirements.md file to user before any DynamoDB modeling

**CRITICAL**: Never proceed to DynamoDB modeling without first creating mysql_requirements.md

## RULES
- Use ONLY the numbered templates above
- Replace ONLY [BRACKETED_PLACEHOLDERS] with actual values  
- NEVER create custom SQL queries
- NEVER modify template structure
- NEVER use "simpler approaches"
