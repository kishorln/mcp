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

### TEMPLATE 3 - PATTERN ANALYSIS (CONFIGURABLE)
```sql
SELECT 
  CONVERT(argument USING utf8) as query_pattern,
  COUNT(*) as frequency,
  COUNT(DISTINCT user_host) as unique_users,
  MIN(event_time) as first_seen,
  MAX(event_time) as last_seen,
  -- Database classification
  CASE 
    -- First: Check for explicit current database prefix
    WHEN CONVERT(argument USING utf8) LIKE '%[TARGET_DATABASE].%' THEN 'primary_db'
    -- Second: Check if references current database tables
    WHEN EXISTS (
      SELECT 1 FROM information_schema.TABLES t 
      WHERE t.TABLE_SCHEMA = '[TARGET_DATABASE]'
      AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
    ) THEN 'primary_db'
    -- Third: Check for actual cross-database (validate database name exists)
    WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
         AND EXISTS (
           SELECT 1 FROM information_schema.SCHEMATA s
           WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
           AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
           AND s.SCHEMA_NAME != '[TARGET_DATABASE]'
         ) THEN 'cross_db'
    ELSE 'no_db_prefix'
  END as query_type,
  -- Complexity classification
  CASE 
    WHEN UPPER(CONVERT(argument USING utf8)) REGEXP '^SELECT.*FROM [a-zA-Z_][a-zA-Z0-9_]* WHERE' 
         AND UPPER(CONVERT(argument USING utf8)) NOT LIKE '%JOIN%' 
         AND UPPER(CONVERT(argument USING utf8)) NOT LIKE '%SELECT.*FROM.*SELECT%' THEN 'Single Table Search'
    WHEN UPPER(CONVERT(argument USING utf8)) LIKE '%JOIN%' 
         AND UPPER(CONVERT(argument USING utf8)) NOT LIKE '%SELECT.*FROM.*SELECT%' THEN 'JOIN Query'
    WHEN UPPER(CONVERT(argument USING utf8)) LIKE '%JOIN%' 
         AND (UPPER(CONVERT(argument USING utf8)) LIKE '%GROUP BY%' OR UPPER(CONVERT(argument USING utf8)) LIKE '%ORDER BY%' 
              OR UPPER(CONVERT(argument USING utf8)) LIKE '%HAVING%') THEN 'Complex JOIN'
    WHEN UPPER(CONVERT(argument USING utf8)) REGEXP '^CALL [a-zA-Z_][a-zA-Z0-9_]*' THEN 'Stored Procedure'
    WHEN UPPER(CONVERT(argument USING utf8)) REGEXP '^SELECT.*FROM [a-zA-Z_][a-zA-Z0-9_]*$' THEN 'Full Table Scan'
    WHEN UPPER(CONVERT(argument USING utf8)) LIKE 'SELECT%' THEN 'Simple SELECT'
    ELSE 'Other'
  END as complexity_type,
  -- Index usage hints
  CASE 
    WHEN CONVERT(argument USING utf8) LIKE '%WHERE%id%=%' THEN 'Likely Primary Key'
    WHEN CONVERT(argument USING utf8) LIKE '%WHERE%' AND CONVERT(argument USING utf8) LIKE '%=%' THEN 'Likely Indexed'
    WHEN CONVERT(argument USING utf8) LIKE '%WHERE%' AND CONVERT(argument USING utf8) LIKE '%LIKE%' THEN 'Potential Full Scan'
    ELSE 'Unknown Index Usage'
  END as index_usage_hint
FROM mysql.general_log 
WHERE command_type = 'Query'
  AND event_time >= DATE_SUB(NOW(), INTERVAL [ANALYSIS_DAYS] DAY)
  AND user_host NOT LIKE '%rdsadmin%'
  AND user_host NOT LIKE '%system%'
  -- User filtering: Replace with specific user if [USER_FILTER] != "ALL"
  AND ([USER_FILTER] = 'ALL' OR user_host LIKE '%[USER_FILTER]%')
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
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT [TARGET_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'use [TARGET_DATABASE]%'
  AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'DESCRIBE %'
  AND CONVERT(argument USING utf8) NOT LIKE 'EXPLAIN %'
  AND CONVERT(argument USING utf8) NOT LIKE '# Press run%'
  AND (
    CONVERT(argument USING utf8) LIKE '%[TARGET_DATABASE].%' 
    OR CONVERT(argument USING utf8) LIKE 'USE [TARGET_DATABASE]%'
    OR (
      CONVERT(argument USING utf8) NOT LIKE '%.%' 
      AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
      AND EXISTS (
        SELECT 1 FROM information_schema.TABLES t 
        WHERE t.TABLE_SCHEMA = '[TARGET_DATABASE]'
        AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
      )
    )
    OR (
      CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
      AND EXISTS (
        SELECT 1 FROM information_schema.SCHEMATA s
        WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
        AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
        AND s.SCHEMA_NAME != '[TARGET_DATABASE]'
      )
    )
  )
GROUP BY CONVERT(argument USING utf8), query_type
ORDER BY frequency DESC
LIMIT 50;
```

### TEMPLATE 4A - TABLE ANALYSIS
```sql
SELECT 
  TABLE_NAME,
  TABLE_ROWS,
  ROUND(DATA_LENGTH/1024/1024, 2) as datamb,
  ROUND(INDEX_LENGTH/1024/1024, 2) as indexmb,
  (SELECT COUNT(*) FROM information_schema.COLUMNS c WHERE c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME) as columncount,
  (SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE k WHERE k.TABLE_SCHEMA = t.TABLE_SCHEMA AND k.TABLE_NAME = t.TABLE_NAME AND k.REFERENCED_TABLE_NAME IS NOT NULL) as fkcount,
  CREATE_TIME,
  UPDATE_TIME
FROM information_schema.TABLES t
WHERE TABLE_SCHEMA = '[TARGET_DATABASE]'
ORDER BY TABLE_ROWS DESC;
```

### TEMPLATE 4B - COLUMN INFORMATION
```sql
SELECT 
  TABLE_NAME,
  COLUMN_NAME, 
  COLUMN_TYPE, 
  IS_NULLABLE, 
  COLUMN_KEY, 
  COLUMN_DEFAULT, 
  EXTRA
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = '[TARGET_DATABASE]' 
ORDER BY TABLE_NAME, ORDINAL_POSITION;
```

### TEMPLATE 4C - INDEX STATISTICS
```sql
SELECT 
  TABLE_NAME, 
  INDEX_NAME, 
  COLUMN_NAME, 
  NON_UNIQUE, 
  SEQ_IN_INDEX
FROM information_schema.STATISTICS 
WHERE TABLE_SCHEMA = '[TARGET_DATABASE]'
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
```

### TEMPLATE 4D - FOREIGN KEY ANALYSIS
```sql
SELECT 
  kcu.CONSTRAINT_NAME,
  kcu.TABLE_NAME as child_table,
  kcu.COLUMN_NAME as child_column,
  kcu.REFERENCED_TABLE_NAME as parent_table,
  kcu.REFERENCED_COLUMN_NAME as parent_column,
  rc.UPDATE_RULE,
  rc.DELETE_RULE,
  CASE 
    WHEN EXISTS (
      SELECT 1 FROM information_schema.STATISTICS s 
      WHERE s.TABLE_SCHEMA = '[TARGET_DATABASE]' 
      AND s.TABLE_NAME = kcu.TABLE_NAME 
      AND s.COLUMN_NAME = kcu.COLUMN_NAME 
      AND s.NON_UNIQUE = 0
    ) THEN '1:1 or 1:0..1'
    ELSE '1:Many'
  END as estimated_cardinality
FROM information_schema.KEY_COLUMN_USAGE kcu
LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc 
  ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME 
  AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
WHERE kcu.TABLE_SCHEMA = '[TARGET_DATABASE]'
  AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY kcu.TABLE_NAME, kcu.COLUMN_NAME;
```

### TEMPLATE 4E - DATABASE OBJECTS
```sql
SELECT 
  'Tables' as object_type,
  COUNT(*) as count,
  GROUP_CONCAT(TABLE_NAME) as names
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = '[TARGET_DATABASE]'
UNION ALL
SELECT 
  'Triggers' as object_type,
  COUNT(*) as count,
  COALESCE(GROUP_CONCAT(TRIGGER_NAME), 'None') as names
FROM information_schema.TRIGGERS 
WHERE TRIGGER_SCHEMA = '[TARGET_DATABASE]'
UNION ALL
SELECT 
  'Stored Procedures' as object_type,
  COUNT(*) as count,
  COALESCE(GROUP_CONCAT(ROUTINE_NAME), 'None') as names
FROM information_schema.ROUTINES 
WHERE ROUTINE_SCHEMA = '[TARGET_DATABASE]' 
AND ROUTINE_TYPE = 'PROCEDURE'
UNION ALL
SELECT 
  'Functions' as object_type,
  COUNT(*) as count,
  COALESCE(GROUP_CONCAT(ROUTINE_NAME), 'None') as names
FROM information_schema.ROUTINES 
WHERE ROUTINE_SCHEMA = '[TARGET_DATABASE]' 
AND ROUTINE_TYPE = 'FUNCTION';
```

### TEMPLATE 5A - TRAFFIC ANALYSIS
```sql
-- Traffic analysis focused on RPS, timing, and volume (configurable period)
SELECT 
  DATE(event_time) as analysis_date,
  HOUR(event_time) as analysis_hour,
  COUNT(*) as total_queries,
  COUNT(*) / 3600 as avg_rps_this_hour,
  COUNT(DISTINCT user_host) as unique_users,
  -- Query type breakdown
  COUNT(CASE WHEN CONVERT(argument USING utf8) LIKE '%[TARGET_DATABASE].%' THEN 1 END) as primary_db_queries,
  COUNT(CASE WHEN CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*' 
              AND CONVERT(argument USING utf8) NOT LIKE '%[TARGET_DATABASE].%' THEN 1 END) as cross_db_queries
FROM mysql.general_log 
WHERE event_time >= DATE_SUB(NOW(), INTERVAL [ANALYSIS_DAYS] DAY)
  AND command_type = 'Query'
  AND user_host NOT LIKE '%rdsadmin%'
  AND user_host NOT LIKE '%system%'
  -- User filtering
  AND ([USER_FILTER] = 'ALL' OR user_host LIKE '%[USER_FILTER]%')
  -- Apply same filters as pattern analysis
  AND CONVERT(argument USING utf8) NOT LIKE 'SET %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SHOW %'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT @@%'
  AND CONVERT(argument USING utf8) NOT LIKE 'SELECT 1'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.general_log%'
  AND CONVERT(argument USING utf8) NOT LIKE '%information_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%performance_schema%'
  AND CONVERT(argument USING utf8) NOT LIKE '%mysql.%'
  AND CONVERT(argument USING utf8) NOT LIKE '%sys.%'
  AND (
    -- Include primary database queries
    CONVERT(argument USING utf8) LIKE '%[TARGET_DATABASE].%' 
    OR CONVERT(argument USING utf8) LIKE 'USE [TARGET_DATABASE]%'
    OR (
      CONVERT(argument USING utf8) NOT LIKE '%.%' 
      AND CONVERT(argument USING utf8) NOT LIKE 'USE %'
      AND EXISTS (
        SELECT 1 FROM information_schema.TABLES t 
        WHERE t.TABLE_SCHEMA = '[TARGET_DATABASE]' 
        AND CONVERT(argument USING utf8) REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
      )
    )
    -- Include cross-database queries
    OR (
      CONVERT(argument USING utf8) REGEXP '[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*'
      AND CONVERT(argument USING utf8) NOT LIKE '%[TARGET_DATABASE].%'
      AND EXISTS (
        SELECT 1 FROM information_schema.SCHEMATA s
        WHERE CONVERT(argument USING utf8) REGEXP CONCAT('\\b', s.SCHEMA_NAME, '\\.[a-zA-Z_][a-zA-Z0-9_]*\\b')
        AND s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
        AND s.SCHEMA_NAME != '[TARGET_DATABASE]'
      )
    )
  )
GROUP BY DATE(event_time), HOUR(event_time)
ORDER BY analysis_date DESC, analysis_hour DESC;
```

### TEMPLATE 5B - OVERALL RPS CALCULATION
```sql
SELECT 
  COUNT(*) as total_queries_in_period,
  COUNT(*) / ([ANALYSIS_DAYS] * 24 * 3600) as average_rps,
  MAX(hourly_queries) as peak_hourly_queries,
  MAX(hourly_queries) / 3600 as peak_rps
FROM (
  SELECT DATE(event_time), HOUR(event_time), COUNT(*) as hourly_queries
  FROM mysql.general_log 
  WHERE event_time >= DATE_SUB(NOW(), INTERVAL [ANALYSIS_DAYS] DAY)
    AND command_type = 'Query'
    AND CONVERT(argument USING utf8) NOT LIKE '/* RDS Data API */%'
    AND user_host NOT LIKE '%rdsadmin%'
    AND user_host NOT LIKE '%system%'
    -- User filtering
    AND ([USER_FILTER] = 'ALL' OR user_host LIKE '%[USER_FILTER]%')
    AND argument NOT LIKE 'SET %'
    AND argument NOT LIKE 'SHOW %'
    AND argument NOT LIKE 'SELECT @@%'
    AND argument NOT LIKE 'SELECT 1'
    AND argument NOT LIKE '%mysql.general_log%'
    AND argument NOT LIKE 'SELECT [TARGET_DATABASE]%'
    AND argument NOT LIKE '%frequency%RPS%'
    AND (
      argument LIKE CONCAT('%', '[TARGET_DATABASE]', '.%') 
      OR argument LIKE CONCAT('USE ', '[TARGET_DATABASE]' , '%')
      OR (
        argument NOT LIKE '%.%' 
        AND argument NOT LIKE 'USE %'
        AND EXISTS (
          SELECT 1 FROM information_schema.TABLES t 
          WHERE t.TABLE_SCHEMA = '[TARGET_DATABASE]' 
          AND argument REGEXP CONCAT('\\b', t.TABLE_NAME, '\\b')
        )
        AND NOT EXISTS (
          SELECT 1 FROM information_schema.TABLES t2
          WHERE t2.TABLE_SCHEMA != '[TARGET_DATABASE]'
          AND t2.TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
          AND argument REGEXP CONCAT('\\b', t2.TABLE_NAME, '\\b')
        )
      )
    )
  GROUP BY DATE(event_time), HOUR(event_time)
) AS hourly_stats;
```

### TEMPLATE 6 - MYSQL REQUIREMENTS FILE
```markdown
# MySQL Database Analysis Results

## Analysis Metadata
- **Analysis Date**: [CURRENT_TIMESTAMP]
- **Source Database**: [TARGET_DATABASE]
- **Analysis Period**: [ANALYSIS_DAYS] Days
- **User Scope**: [USER_FILTER] ([ALL users] or [specific username])
- **Cross-Database Included**: [TRUE if cross_db_patterns > 0, otherwise FALSE]
- **Total Patterns Found**: [MEANINGFUL_PATTERN_COUNT]
- **Analysis Step**: [SUCCESSFUL_STEP_NUMBER]

## Database Schema Summary

### Tables Analyzed
| Table | Rows | Data Size (MB) | Index Size (MB) | Columns | Foreign Keys | Auto Increment | Created |
|-------|------|----------------|-----------------|---------|--------------|----------------|---------|
[Table analysis with column counts, FK counts, auto-increment detection, creation dates]

### Database Objects Summary
| Object Type | Count | Names |
|-------------|-------|-------|
| Triggers | [count] | [list trigger names or 'None'] |
| Stored Procedures | [count] | [list procedure names or 'None'] |
| Functions | [count] | [list function names or 'None'] |

### Relationships Detected
#### Foreign Key Relationships
| Child Table | Child Column | Parent Table | Parent Column | Cardinality | Update Rule | Delete Rule |
|-------------|--------------|--------------|---------------|-------------|-------------|-------------|
[List all foreign key relationships with rules and estimated cardinality from analysis]

## Access Patterns Discovered

### Pattern Summary
| Pattern # | Original MySQL Query | Frequency | RPS | Users | Complexity Type | Index Usage | First Seen | Last Seen |
|-----------|---------------------|-----------|-----|-------|-----------------|-------------|------------|-----------|
[List all discovered patterns with metrics from integrated complexity analysis]

### High Frequency Patterns (>1.0 RPS)
[For each high-frequency pattern, include:]
- **Original SQL**: `[exact query from mysql.general_log]`
- **Frequency**: [count] queries over 90 Days
- **Calculated RPS**: [frequency / time_period_seconds]
- **Unique Users**: [count of distinct user_host values]
- **Complexity**: [Single Table Search/JOIN Query/Complex JOIN/etc.]
- **Index Usage**: [Likely Primary Key/Likely Indexed/Potential Full Scan/Unknown]
- **Time Range**: [first_seen] to [last_seen]

### Medium Frequency Patterns (0.01-1.0 RPS)
[Same format for medium frequency patterns]

### Low Frequency Patterns (<0.01 RPS)
[Same format for low frequency patterns]

## Traffic Analysis

### Overall Statistics
- **Total RPS**: [sum of all pattern RPS]
- **Peak Hour**: [hour with highest activity from traffic analysis]
- **Read/Write Ratio**: [read_write_ratio]
- **Unique Users**: [count from query logs]
- **Analysis Period**: 90 days

### Database Scope
- **Primary Database Queries**: [primary_db_queries count] ([percentage]%)
- **Cross-Database Queries**: [cross_db_queries count] ([percentage]%)

### Data Volume Analysis
[For each table from comprehensive profiling:]
- **[TableName]**: [row_count] records, [data_size_mb] MB data, [index_size_mb] MB indexes, [column_count] columns, [fk_count] foreign keys

## Cross-Database Analysis
[IF cross_db_patterns > 0:]
### Multi-Database Patterns Found
[List cross-database patterns with referenced databases]

[IF cross_db_patterns = 0:]
No cross-database patterns detected. Analysis focused on: [CONFIGURED_DATABASE]

## Technical Notes

### Analysis Quality
- **Query Log Coverage**: [based on general_log availability and time period]
- **Pattern Detection Method**: Automated from mysql.general_log with integrated complexity classification
- **RPS Calculation**: Query frequency divided by analysis period seconds
- **Schema Source**: information_schema tables with relationship analysis
- **Confidence Level**: [High/Medium/Low based on data completeness and pattern count]

### Limitations
- **Sample Period**: [actual period that provided sufficient meaningful patterns]
- **Missing Patterns**: [potential patterns not captured in logs during analysis period]
- **System Queries**: Excluded from analysis with comprehensive filtering
- **Complexity Classification**: Based on SQL structure analysis for DynamoDB migration planning

### Migration Considerations
- **Foreign Key Dependencies**: [count] relationships detected requiring DynamoDB design consideration
- **Complex Queries**: [count] JOIN/Complex patterns requiring access pattern redesign
- **Data Volume**: [total_size_mb] MB total database size suitable for DynamoDB migration

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

### Step 0.5: Analysis Configuration
After confirming general log is enabled, ask the user:

**🔧 Analysis Configuration Questions:**

1. **Database Selection**: 
   - "The configured database is `[CONFIGURED_DATABASE]` (default). Do you want to analyze this database or specify a different one?"
   - If different: "Please provide the database name to analyze:"

2. **Analysis Period**:
   - "What time period should I analyze? (Default: 90 days)"
   - Options: "[X] days", "[X] months", "[X] years"
   - Convert to days: months×30, years×365

3. **User Scope**:
   - "Which users should I include in the analysis?"
   - Options: "All users (default)" or "Specific user: [username]"

**🚨 CRITICAL: STOP HERE AND WAIT FOR USER RESPONSE**
**DO NOT PROCEED WITH ANY QUERIES UNTIL USER CONFIRMS CONFIGURATION**
**DO NOT USE DEFAULT VALUES WITHOUT EXPLICIT USER CONSENT**

**Store these values as:**
- `[TARGET_DATABASE]` - Database to analyze
- `[ANALYSIS_DAYS]` - Number of days to analyze  
- `[USER_FILTER]` - Either "ALL" or specific username

**IMPORTANT**: In all queries, replace `[TARGET_DATABASE]`, `[ANALYSIS_DAYS]` and `[USER_FILTER]` with actual user values or default if no concerns from user.

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

### Step 1: Pattern Analysis (Configurable Users and Period)

**MANDATORY**: Execute TEMPLATE 3 - PATTERN ANALYSIS (CONFIGURABLE)
- Replace [TARGET_DATABASE] with the database name from configuration
- Replace [ANALYSIS_DAYS] with the configured analysis period
- Replace [USER_FILTER] with 'ALL' or specific username from configuration
- Execute the complete query exactly as written
- Store results

**🔍 IMMEDIATE INSIGHTS AFTER STEP 1:**
After executing TEMPLATE 3, provide these insights to the user:

```
🔍 **Pattern Analysis Insights:**

📊 **Query Patterns Discovered**: [X] distinct patterns found
📈 **Peak RPS**: [highest_rps] for [top_pattern_description]
👥 **User Activity**: [unique_users] unique users, [user_scope_description]
🏗️ **Application Type**: [inferred from query patterns - e.g., "Social media platform", "E-commerce", "CRM system"]
📝 **Read/Write Ratio**: [X]% reads, [Y]% writes - [assessment of workload type]
🔥 **Top Patterns**:
   1. [Pattern 1]: [frequency] queries ([users] users) - [business meaning]
   2. [Pattern 2]: [frequency] queries ([users] users) - [business meaning]
   3. [Pattern 3]: [frequency] queries ([users] users) - [business meaning]

🗄️ **Database Scope**:
   - Primary DB queries: [primary_db_count] ([percentage]%)
   - Cross-DB queries: [cross_db_count] ([percentage]%) - [assessment if significant]

💡 **Migration Readiness**: [assessment based on pattern complexity]
⚠️ **Complexity Concerns**: [JOIN patterns, stored procedures, complex queries that need attention]
```

### Step 2: Schema Analysis

**MANDATORY**: Execute ALL 5 templates separately:
1. Execute TEMPLATE 4A - TABLE ANALYSIS
2. Execute TEMPLATE 4B - COLUMN INFORMATION  
3. Execute TEMPLATE 4C - INDEX STATISTICS
4. Execute TEMPLATE 4D - FOREIGN KEY ANALYSIS
5. Execute TEMPLATE 4E - DATABASE OBJECTS
- Replace [TARGET_DATABASE] in all queries
- Store all schema results

**🔍 IMMEDIATE INSIGHTS AFTER STEP 2:**
After executing all TEMPLATE 4 queries, provide these insights:

```
🔍 **Schema Analysis Insights:**

🗃️ **Database Structure**: [X] tables, [Y] total records, [Z] MB total size
📊 **Entity Relationships**: [X] foreign key relationships detected
🏗️ **Application Domain**: [detailed assessment based on table names and relationships]
📈 **Data Distribution**:
   - Largest table: [table_name] ([row_count] records, [size] MB)
   - Most connected: [table_name] ([fk_count] relationships)
   - Growth patterns: [analysis of data volume per table]

🔗 **Key Relationships Identified**:
   - [Parent] → [Child]: [cardinality] ([business meaning])
   - [Entity1] ↔ [Entity2]: [relationship type] ([business meaning])

🛠️ **Migration Complexity**:
   - ✅ Clean schema: [no triggers/procedures] OR ⚠️ Complex objects: [X triggers, Y procedures]
   - 🎯 DynamoDB Suitability: [assessment based on relationships and data patterns]
   - 📋 Consolidation Opportunities: [potential item collections identified]

🔧 **Development Environment Notes**:
   - Non-production analysis: [implications for production migration]
   - Data volume: [assessment if representative of production]
```

### Step 3: Traffic Analysis

**MANDATORY**: Execute BOTH templates separately:
1. Execute TEMPLATE 5A - TRAFFIC ANALYSIS
2. Execute TEMPLATE 5B - OVERALL RPS CALCULATION
- Replace [TARGET_DATABASE], [ANALYSIS_DAYS], and [USER_FILTER] in both queries
- Store all traffic results

**🔍 IMMEDIATE INSIGHTS AFTER STEP 3:**
After executing TEMPLATE 5A and 5B, provide these insights:

```
🔍 **Traffic Analysis Insights:**

⏰ **Activity Timeline**: Peak activity during [time_range] with [peak_rps] RPS
📊 **Load Distribution**: [analysis of traffic patterns across time]
👥 **User Patterns**: [analysis of user activity and distribution]
🎯 **Engagement Patterns**: [business insights from traffic timing]
🔥 **Hot Patterns**: [patterns with highest frequency and their business meaning]

📈 **Scalability Assessment**:
   - Current load: [total_rps] RPS across all patterns
   - DynamoDB readiness: [assessment of whether current load suits DynamoDB]
   - Production projection: [estimated scaling needs for production environment]

💰 **Cost Implications**:
   - Read-heavy: [X]% reads → [cost optimization strategies]
   - Write patterns: [Y]% writes → [counter patterns, hot partition risks]
   - Data access: [correlation analysis for item collections]

🚧 **Non-Production Considerations**:
   - Development traffic: [assessment of how representative this is of production]
   - User simulation: [analysis of whether patterns reflect real usage]
   - Scaling factors: [recommendations for production capacity planning]

🚀 **Next Steps Ready**: Schema + Patterns + Traffic = Complete migration foundation

**🔧 USER CONFIRMATION REQUIRED:**
"I've completed the comprehensive MySQL analysis with [X] query patterns, [Y] tables, and [Z] relationships discovered from your database.

Would you like me to:
1. **Create the requirements file** with these analysis results and proceed to DynamoDB modeling
2. **Make adjustments** to the analysis (different time period, user scope, or database focus)
3. **Review specific patterns** before finalizing the requirements

Please confirm how you'd like to proceed."

**🚨 CRITICAL: STOP HERE AND WAIT FOR USER RESPONSE**
**DO NOT CREATE mysql_requirements.md UNTIL USER CONFIRMS**
```

### Final Output
**MANDATORY**: Create mysql_requirements.md file ONLY after ALL queries execute successfully
1. Use TEMPLATE 6 - MYSQL REQUIREMENTS FILE to create mysql_requirements.md
2. Replace all placeholders with actual analysis results from pattern, schema, and traffic analysis
3. **CONNECTION ISSUES**: If queries fail due to connection/timeout issues, ask user to fix connection and retry - DO NOT create requirements file with incomplete data
4. **INSUFFICIENT DATA**: Only mark sections as "Insufficient data" if queries execute but return no results
5. Provide completed mysql_requirements.md file to user before any DynamoDB modeling

**CRITICAL**: Never proceed to DynamoDB modeling without first creating complete mysql_requirements.md

## STRICT ENFORCEMENT RULES

🚨 **CRITICAL WORKFLOW ENFORCEMENT** 🚨

### MANDATORY TEMPLATE EXECUTION ORDER
**YOU MUST EXECUTE EVERY TEMPLATE IN EXACT ORDER - NO EXCEPTIONS**

**Step 0: Database Setup (2 templates + configuration)**
- ✅ TEMPLATE 1 - DATABASE IDENTIFICATION (MANDATORY)
- ✅ TEMPLATE 2 - GENERAL LOG CHECK (MANDATORY)
- ✅ STEP 0.5 - ANALYSIS CONFIGURATION (MANDATORY)

**Step 1: Pattern Analysis (1 template)**  
- ✅ TEMPLATE 3 - PATTERN ANALYSIS (CONFIGURABLE) (MANDATORY)

**Step 2: Schema Analysis (5 templates - ALL REQUIRED)**
- ✅ TEMPLATE 4A - TABLE ANALYSIS (MANDATORY)
- ✅ TEMPLATE 4B - COLUMN INFORMATION (MANDATORY)  
- ✅ TEMPLATE 4C - INDEX STATISTICS (MANDATORY)
- ✅ TEMPLATE 4D - FOREIGN KEY ANALYSIS (MANDATORY)
- ✅ TEMPLATE 4E - DATABASE OBJECTS (MANDATORY)

**Step 3: Traffic Analysis (2 templates - BOTH REQUIRED)**
- ✅ TEMPLATE 5A - TRAFFIC ANALYSIS (MANDATORY)
- ✅ TEMPLATE 5B - OVERALL RPS CALCULATION (MANDATORY)

**Step 4: Final Output (1 template)**
- ✅ TEMPLATE 6 - MYSQL REQUIREMENTS FILE (MANDATORY)

### VIOLATION PREVENTION RULES
- ❌ **NEVER SKIP ANY TEMPLATE** - Each template provides critical data
- ❌ **NEVER COMBINE TEMPLATES** - Execute each template separately  
- ❌ **NEVER CREATE CUSTOM SQL** - Use exact templates only
- ❌ **NEVER MODIFY TEMPLATE STRUCTURE** - Copy templates exactly
- ❌ **NEVER USE "SIMPLER APPROACHES"** - Templates are optimized
- ❌ **NEVER PROCEED WITHOUT ALL DATA** - All 11 templates must complete

### CHECKPOINT ENFORCEMENT
**Before proceeding to next step, confirm:**
- [ ] All templates in current step executed successfully
- [ ] All results stored and available
- [ ] No templates skipped or modified
- [ ] Ready to proceed to next mandatory step

### COMPLETION VERIFICATION
**Before creating mysql_requirements.md file:**
- [ ] Step 0: Templates 1-2 completed ✅
- [ ] Step 1: Template 3 completed ✅  
- [ ] Step 2: Templates 4A-4E completed ✅
- [ ] Step 3: Templates 5A-5B completed ✅
- [ ] All 10 SQL templates executed successfully ✅
- [ ] Ready to create Template 6 requirements file ✅

## RULES
- Use ONLY the numbered templates above
- Replace ONLY [BRACKETED_PLACEHOLDERS] with actual values  
- NEVER create custom SQL queries
- NEVER modify template structure
- NEVER use "simpler approaches"
- **EXECUTE ALL 11 TEMPLATES IN ORDER - NO EXCEPTIONS**
