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
SHOW VARIABLES LIKE 'performance_schema';
```

### TEMPLATE 3 - PATTERN ANALYSIS (PERFORMANCE SCHEMA CONFIGURABLE)
```sql
SELECT 
  DIGEST_TEXT as query_pattern,
  COUNT_STAR as frequency,
  ROUND(COUNT_STAR / ([ANALYSIS_DAYS] * 24 * 3600), 4) as calculated_rps,
  ROUND(AVG_TIMER_WAIT/1000000000, 6) as avg_execution_time,
  ROUND(SUM_ROWS_EXAMINED/COUNT_STAR, 1) as avg_rows_per_query,
  SUM_SELECT_SCAN as full_table_scans,
  SUM_SELECT_FULL_JOIN as full_joins,
  FIRST_SEEN as first_seen,
  LAST_SEEN as last_seen,
  -- Complexity classification
  CASE 
    WHEN DIGEST_TEXT LIKE 'SELECT%FROM%WHERE%' AND DIGEST_TEXT NOT LIKE '%JOIN%' THEN 'Single Table Search'
    WHEN DIGEST_TEXT LIKE '%JOIN%' THEN 'JOIN Query'
    WHEN DIGEST_TEXT LIKE '%JOIN%' 
        AND (DIGEST_TEXT LIKE '%GROUP BY%' OR DIGEST_TEXT LIKE '%ORDER BY%' 
            OR DIGEST_TEXT LIKE '%HAVING%') THEN 'Complex JOIN'
    WHEN DIGEST_TEXT REGEXP '^CALL [a-zA-Z_][a-zA-Z0-9_]*' THEN 'Stored Procedure'
    WHEN DIGEST_TEXT LIKE 'SELECT%' THEN 'Simple SELECT'
    ELSE 'Other'
  END as complexity_type,
    -- Index usage hints
  CASE 
    WHEN DIGEST_TEXT LIKE '%WHERE%id%=%' THEN 'Likely Primary Key'
    WHEN DIGEST_TEXT LIKE '%WHERE%' AND DIGEST_TEXT LIKE '%=%' THEN 'Likely Indexed'
    WHEN DIGEST_TEXT LIKE '%WHERE%' AND DIGEST_TEXT LIKE '%LIKE%' THEN 'Potential Full Scan'
    ELSE 'Unknown Index Usage'
  END as index_usage_hint
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = '[TARGET_DATABASE]'
AND COUNT_STAR > 5
AND LAST_SEEN >= DATE_SUB(NOW(), INTERVAL [ANALYSIS_DAYS] DAY)
AND DIGEST_TEXT NOT LIKE 'SET%'
AND DIGEST_TEXT NOT LIKE 'USE %'
AND DIGEST_TEXT NOT LIKE 'SHOW%'
AND DIGEST_TEXT NOT LIKE '/* RDS Data API */%'
AND DIGEST_TEXT NOT LIKE '%information_schema%'
AND DIGEST_TEXT NOT LIKE '%performance_schema%'
AND DIGEST_TEXT NOT LIKE '%mysql.%'
AND DIGEST_TEXT NOT LIKE 'SELECT @@%'
AND DIGEST_TEXT NOT LIKE '%sys.%'
AND DIGEST_TEXT NOT LIKE 'select ?'
AND DIGEST_TEXT NOT LIKE '%mysql.general_log%'
AND DIGEST_TEXT NOT LIKE 'DESCRIBE %'
AND DIGEST_TEXT NOT LIKE 'EXPLAIN %'
AND DIGEST_TEXT NOT LIKE 'configured_database'
ORDER BY frequency DESC;
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

### TEMPLATE 5A - OVERALL RPS CALCULATION
```sql
-- Traffic analysis focused on RPS, timing, and volume (configurable period)
SELECT 
  DATE(LAST_SEEN) as analysis_date,
  HOUR(LAST_SEEN) as analysis_hour,
  SUM(COUNT_STAR) as total_queries,
  SUM(COUNT_STAR) / 3600 as avg_rps_this_hour,
  COUNT(DISTINCT DIGEST) as unique_query_patterns,
  SUM(COUNT_STAR / ([ANALYSIS_DAYS] * 24 * 3600)) as estimated_average_rps,
  MAX(COUNT_STAR) as highest_pattern_frequency,
  COUNT(DISTINCT DIGEST) as unique_query_patterns,
  -- Read/Write breakdown
  SUM(CASE WHEN DIGEST_TEXT LIKE 'SELECT%' THEN COUNT_STAR ELSE 0 END) as read_queries,
  SUM(CASE WHEN DIGEST_TEXT NOT LIKE 'SELECT%' THEN COUNT_STAR ELSE 0 END) as write_queries
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = '[TARGET_DATABASE]'
  AND LAST_SEEN >= DATE_SUB(NOW(), INTERVAL [ANALYSIS_DAYS] DAY)
  AND COUNT_STAR > 0
  AND DIGEST_TEXT NOT LIKE 'SET%'
  AND DIGEST_TEXT NOT LIKE 'USE %'
  AND DIGEST_TEXT NOT LIKE 'SHOW%'
  AND DIGEST_TEXT NOT LIKE '/* RDS Data API */%'
  AND DIGEST_TEXT NOT LIKE '%information_schema%'
  AND DIGEST_TEXT NOT LIKE '%performance_schema%'
  AND DIGEST_TEXT NOT LIKE '%mysql.%'
  AND DIGEST_TEXT NOT LIKE 'SELECT @@%'
  AND DIGEST_TEXT NOT LIKE '%sys.%'
  AND DIGEST_TEXT NOT LIKE 'select ?'
  AND DIGEST_TEXT NOT LIKE '%mysql.general_log%'
  AND DIGEST_TEXT NOT LIKE 'DESCRIBE %'
  AND DIGEST_TEXT NOT LIKE 'EXPLAIN %'
  AND DIGEST_TEXT NOT LIKE 'configured_database'
GROUP BY DATE(LAST_SEEN), HOUR(LAST_SEEN)
ORDER BY analysis_date DESC, analysis_hour DESC;
```

### TEMPLATE 6 - MYSQL REQUIREMENTS FILE
```markdown
# MySQL Database Analysis Results

## Analysis Metadata
- **Analysis Date**: [CURRENT_TIMESTAMP]
- **Source Database**: [TARGET_DATABASE]
- **Analysis Period**: [ANALYSIS_DAYS] Days
- **Total Patterns Found**: [MEANINGFUL_PATTERN_COUNT]

## Database Schema Summary

### Tables Analyzed
| Table | Rows | Data Size (MB) | Index Size (MB) | Columns | Foreign Keys | Auto Increment |
|-------|------|----------------|-----------------|---------|--------------|----------------|
[Table analysis with column counts, FK counts, auto-increment detection]

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

### Entity Relationship Diagram

[Create ERD diagram using mermaid syntax. Start with: erDiagram, then include all tables from TEMPLATE 4A with their columns from TEMPLATE 4B and relationships from TEMPLATE 4D. Show primary keys (PK), foreign keys (FK), and unique keys (UK). Include relationship cardinalities and connection labels.]

### Access Pattern Flow Diagram

[Create access pattern flow diagram using mermaid syntax. Start with: flowchart TD, then show how user actions trigger database operations, connecting high-frequency patterns and showing the flow from user interactions to database queries based on TEMPLATE 3 results.]

## Access Patterns Discovered

### Pattern Summary
| Pattern # | Original MySQL Query (Normalized) | Frequency | RPS | Complexity Type | Index Usage |
|-----------|---------------------|-----------|-----|-------|-----------------|-------------|
[List all discovered patterns with metrics from integrated complexity analysis]

### High Frequency Patterns (>1.0 RPS)
[For each high-frequency pattern, include:]
- **Original SQL**: `[exact query from mysql.general_log]`
- **Frequency**: [count] queries over [ANALYSIS_DAYS] Days
- **Calculated RPS**: [frequency / time_period_seconds]
- **Unique Users**: [count of distinct user_host values]
- **Complexity**: [Single Table Search/JOIN Query/Complex JOIN/etc.]
- **Index Usage**: [Likely Primary Key/Likely Indexed/Potential Full Scan/Unknown]
- **Time Range**: [first_seen] to [last_seen]

### Medium Frequency Patterns (0.01-1.0 RPS)
[Same format for medium frequency patterns]

### Low Frequency Patterns (<0.01 RPS)
[Same format for low frequency patterns]

## RPS Analysis

### Overall Statistics
- **Analysis Date Range**: [ANALYSIS_DATE] ([ANALYSIS_FIRST_HOUR]:00 to [ANALYSIS_LAST_HOUR]:00)
- **Total Queries Analyzed**: [TOTAL_QUERIES] queries over [ANALYSIS_DAYS] days
- **Peak Hour RPS**: [AVG_RPS_THIS_HOUR] (during peak activity period)
- **Estimated Average RPS**: [ESTIMATED_AVERAGE_RPS] (sustained load)
- **Highest Pattern Frequency**: [HIGHEST_PATTERN_FREQUENCY] executions
- **Unique Query Patterns**: [UNIQUE_QUERY_PATTERNS] distinct patterns
- **Read/Write Distribution**: [READ_QUERIES] reads ([READ_PERCENTAGE]%) / [WRITE_QUERIES] writes ([WRITE_PERCENTAGE]%)
- **Analysis Period**: [ANALYSIS_DAYS] days

### Data Volume Analysis
[For each table from comprehensive profiling:]
- **[TableName]**: [row_count] records, [data_size_mb] MB data, [index_size_mb] MB indexes, [column_count] columns, [fk_count] foreign keys

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

### CRITICAL: Analysis Type Determines Workflow Path

**FOR LOG FILE ANALYSIS:**
- Skip all database connection steps (TEMPLATES 1-5A)
- Use log file analysis results directly
- Proceed to TEMPLATE 6 - Create mysql_requirements.md with log analysis data
- DO NOT connect to database or run any SQL queries

**FOR PERFORMANCE SCHEMA ANALYSIS:**
- Follow the complete workflow below (Steps 0-4)

### Step 0: Database Identification (PERFORMANCE SCHEMA ONLY)
1. Execute TEMPLATE 1 - DATABASE IDENTIFICATION
   - If this fails: Provide MySQL MCP configuration instructions below, then STOP

2. Execute TEMPLATE 2 - PERFORMANCE SCHEMA LOG CHECK **ONCE ONLY**
   - If performance_schema is disabled: STOP and provide configuration instructions
   - If successful: Continue with remaining steps
   - **DO NOT EXECUTE ANY ADDITIONAL QUERIES TO "VERIFY" OR "SIMPLIFY" - TEMPLATE 2 IS SUFFICIENT**
 
**CRITICAL**: Do NOT proceed with analysis if MySQL Performance Schema is not enabled.

**AI Response Template for TEMPLATE 2:**
🚨 **EXECUTE TEMPLATE 2 ONCE - DO NOT RUN ADDITIONAL QUERIES**
```
🤖 AI: "Checking MySQL performance_schema status...

Database: [DATABASE_NAME]
Performance Schema Log: [ENABLED/DISABLED]

[IF DISABLED]: ❌ Performance Schema needs configuration for Aurora / RDS MySQL:

📋 RDS MySQL Performance Schema Setup:
1. Open Amazon RDS console → Parameter groups
2. Select your custom parameter group (create one if needed)
3. Set these parameters:
   - performance_schema = 1
4. Associate parameter group with your DB instance
5. Reboot required to make this work

Wait 5-10 minutes for logs to populate, then retry analysis.

[IF ENABLED]: ✅ Performance Schema log is ready for analysis.
```
🚨 **STOP HERE - DO NOT EXECUTE SHOW VARIABLES OR ANY OTHER QUERIES**

**CRITICAL**: If performance_schema is disabled, log_output is not TABLE, or no recent data exists, STOP analysis and provide RDS configuration instructions.

### Step 0.5: Analysis Configuration
After confirming performance schema is enabled, ask the user:

**🔧 Analysis Configuration Questions:**

1. **Database Selection**: 
   - "The configured database is `[CONFIGURED_DATABASE]` (default). Do you want to analyze this database or specify a different one?"
   - If different: "Please provide the database name to analyze:"

2. **Analysis Period**:
   - "What time period should I analyze? (Default: 90 days)"
   - Options: "[X] days", "[X] months", "[X] years"
   - Convert to days: months×30, years×365

**🚨 CRITICAL: STOP HERE AND WAIT FOR USER RESPONSE**
**DO NOT PROCEED WITH ANY QUERIES UNTIL USER CONFIRMS CONFIGURATION**
**DO NOT USE DEFAULT VALUES WITHOUT EXPLICIT USER CONSENT**

**Store these values as:**
- `[TARGET_DATABASE]` - Database to analyze
- `[ANALYSIS_DAYS]` - Number of days to analyze  

**IMPORTANT**: In all queries, replace `[TARGET_DATABASE]`, `[ANALYSIS_DAYS]` with actual user values or default if no concerns from user.

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
- Execute the complete query exactly as written
- Store results

**🚨 MANDATORY INSIGHTS AFTER STEP 1 - CANNOT PROCEED WITHOUT PROVIDING:**
After executing TEMPLATE 3, you MUST provide these insights to the user before proceeding to Step 2:

```
🔍 **Pattern Analysis Insights:**

📊 **Query Patterns Discovered**: [X] distinct patterns found
📈 **Peak RPS**: [highest_rps] for [top_pattern_description]
🏗️ **Application Type**: [inferred from query patterns - e.g., "Social media platform", "E-commerce", "CRM system"]
📝 **Read/Write Ratio**: [X]% reads, [Y]% writes - [assessment of workload type]
🔥 **Top Patterns**:
   1. [Pattern 1]: [frequency] queries ([rps] RPS) - [business meaning]
   2. [Pattern 2]: [frequency] queries ([rps] RPS) - [business meaning]
   3. [Pattern 3]: [frequency] queries ([rps] RPS) - [business meaning]

💡 **Migration Readiness**: [assessment based on pattern complexity]
⚠️ **Complexity Concerns**: [JOIN patterns, stored procedures, complex queries that need attention]
```

🚨 **CHECKPOINT VALIDATION**: Before proceeding to Step 2, confirm you have provided ALL insights above. If any insight is missing, STOP and complete it.

### Step 2: Schema Analysis

**MANDATORY**: Execute ALL 5 templates separately:
1. Execute TEMPLATE 4A - TABLE ANALYSIS
2. Execute TEMPLATE 4B - COLUMN INFORMATION  
3. Execute TEMPLATE 4C - INDEX STATISTICS
4. Execute TEMPLATE 4D - FOREIGN KEY ANALYSIS
5. Execute TEMPLATE 4E - DATABASE OBJECTS
- Replace [TARGET_DATABASE] in all queries
- Store all schema results

**🚨 MANDATORY INSIGHTS AFTER STEP 2 - CANNOT PROCEED WITHOUT PROVIDING:**
After executing all TEMPLATE 4 queries, you MUST provide these insights before proceeding to Step 3:

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
```

🚨 **CHECKPOINT VALIDATION**: Before proceeding to Step 3, confirm you have provided ALL insights above. If any insight is missing, STOP and complete it.

### Step 3: Traffic Analysis

**MANDATORY**: Execute the template below:
1. Execute TEMPLATE 5A - OVERALL RPS CALCULATION
- Replace [TARGET_DATABASE] and [ANALYSIS_DAYS] in both queries
- Store all traffic results

**🚨 MANDATORY INSIGHTS AFTER STEP 3 - CANNOT PROCEED WITHOUT PROVIDING:**
After executing TEMPLATE 5A, you MUST provide these insights before creating the requirements file:

```
🔍 **Traffic Analysis Insights:**

⏰ **Activity Timeline**: Peak activity during [time_range] with [peak_rps] RPS
📊 **Load Distribution**: [analysis of traffic patterns across time]
🎯 **Engagement Patterns**: [business insights from traffic timing]
🔥 **Hot Patterns**: [patterns with highest frequency and their business meaning]

📈 **Scalability Assessment**:
   - Current load: [total_rps] RPS across all patterns
   - DynamoDB readiness: [assessment of whether current load suits DynamoDB]
   - Growth projection: [estimated scaling needs based on current patterns]

💰 **Cost Implications**:
   - Read-heavy: [X]% reads → [cost optimization strategies]
   - Write patterns: [Y]% writes → [counter patterns, hot partition risks]
   - Data access: [correlation analysis for item collections]

🚀 **Next Steps Ready**: Schema + Patterns + Traffic = Complete migration foundation
```

🚨 **CHECKPOINT VALIDATION**: Before creating mysql_requirements.md, confirm you have provided ALL insights above. If any insight is missing, STOP and complete it.

**🔧 USER CONFIRMATION REQUIRED:**
"I've completed the comprehensive MySQL analysis with [X] query patterns, [Y] tables, and [Z] relationships discovered. 

Would you like me to:
1. **Create the requirements file** with these analysis results and proceed to DynamoDB modeling
2. **Make adjustments** to the analysis (different time period, user scope, or database focus)
3. **Review specific patterns** before finalizing the requirements

Please confirm how you'd like to proceed."

**🚨 CRITICAL: STOP HERE AND WAIT FOR USER RESPONSE**
**DO NOT CREATE mysql_requirements.md UNTIL USER CONFIRMS**

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

**Step 3: Traffic Analysis (1 template - REQUIRED)**
- ✅ TEMPLATE 5A - OVERALL RPS CALCULATION (MANDATORY)

**Step 4: Final Output (1 template)**
- ✅ TEMPLATE 6 - MYSQL REQUIREMENTS FILE (MANDATORY)

### MANDATORY INSIGHTS ENFORCEMENT
**🚨 CRITICAL: YOU MUST PROVIDE INSIGHTS AFTER EACH STEP - NO EXCEPTIONS**

**STEP 1 CHECKPOINT**: After TEMPLATE 3 execution → YOU MUST provide Pattern Analysis Insights
**STEP 2 CHECKPOINT**: After TEMPLATE 4A-4E execution → YOU MUST provide Schema Analysis Insights  
**STEP 3 CHECKPOINT**: After TEMPLATE 5A execution → YOU MUST provide Traffic Analysis Insights

**VIOLATION DETECTION**: If you proceed to next step without providing required insights, this is a CRITICAL ERROR.

**ENFORCEMENT MECHANISM**: Each insight section is marked as "🚨 MANDATORY" and includes checkpoint validation.

### CHECKPOINT ENFORCEMENT
**Before proceeding to next step, you MUST confirm:**
- [ ] All templates in current step executed successfully
- [ ] **MANDATORY INSIGHTS PROVIDED** (Pattern/Schema/Traffic as applicable)
- [ ] All results stored and available
- [ ] No templates skipped or modified
- [ ] Ready to proceed to next mandatory step

**🚨 CRITICAL**: If insights are missing, you MUST STOP and provide them before continuing.

### COMPLETION VERIFICATION
**Before creating mysql_requirements.md file, you MUST confirm:**
- [ ] Step 0: Templates 1-2 completed ✅
- [ ] Step 1: Template 3 completed + **Pattern Analysis Insights provided** ✅  
- [ ] Step 2: Templates 4A-4E completed + **Schema Analysis Insights provided** ✅
- [ ] Step 3: Templates 5A completed + **Traffic Analysis Insights provided** ✅
- [ ] All 10 SQL templates executed successfully ✅
- [ ] **ALL MANDATORY INSIGHTS PROVIDED** ✅
- [ ] Ready to create Template 6 requirements file ✅

**🚨 CRITICAL**: If any insights are missing, you MUST provide them before creating the requirements file.

## RULES
- Use ONLY the numbered templates above
- Replace ONLY [BRACKETED_PLACEHOLDERS] with actual values  
- NEVER create custom SQL queries
- NEVER modify template structure
- NEVER use "simpler approaches"
- **EXECUTE ALL 10 TEMPLATES IN ORDER - NO EXCEPTIONS**
