# Source Database Analysis for DynamoDB Data Modeling

## 🔴 CRITICAL: Follow This Exact Workflow

### Analysis Execution Order:

1. **Database Type Selection**:
   - "What type of source database are you analyzing?"
   - Store as `source_db_type`

2. **Database Identification**:
   - `analyze_source_db(source_db_type="[USER_DB_TYPE]", target_database="", query_name="database_identification")`
   - Shows current/default database
   - Then ask user: "The current database is `[CURRENT_DB]`. Would you like to analyze this database or specify a different one?"
   - Store user choice as `target_database`

3. **Analysis Period Configuration**:
   - "How many days of data should I analyze? (Default: 30 days)"
   - Options: 7, 30, 60, 90 days
   - Store as `analysis_days`

4. **Performance Schema Check**:
   - `analyze_source_db(source_db_type="[USER_DB_TYPE]", target_database="[USER_DB]", query_name="[PREREQUISITE_CHECK]")`
   - MySQL: performance_schema_check
   - If Performance Schema is enabled: proceed with pattern_analysis and rps_calculation
   - If Performance Schema is disabled: skip pattern_analysis and rps_calculation, continue with schema analysis

5. **Pattern Analysis** (if Performance Schema enabled):
   - `analyze_source_db(source_db_type="[USER_DB_TYPE]", target_database="[USER_DB]", query_name="[PATTERN_QUERY]", analysis_days=[USER_DAYS])`
   - For MySQL Execute: pattern_analysis

6. **Schema Analysis**:
   - 🔴 **CRITICAL**: Execute `analyze_source_db(source_db_type="[USER_DB_TYPE]", target_database="[USER_DB]", query_name="[QUERY_NAME]")` for EACH query based on database type:

   **MySQL queries:**
     - table_analysis
     - column_analysis
     - index_analysis
     - foreign_key_analysis
     - database_objects

   - You MUST run all queries for the selected database type - do NOT skip any

7. **Traffic Analysis**:
   - `analyze_source_db(source_db_type="[USER_DB_TYPE]", target_database="[USER_DB]", query_name="[TRAFFIC_QUERY]", analysis_days=[USER_DAYS])`
   - For MySQL Execute: rps_calculation (if Performance Schema is enabled)

### 🔴 MANDATORY INSIGHTS AFTER EACH STEP:

**After Pattern Analysis**: 🔴 **REQUIRED** - You MUST provide insights on:
- Query patterns discovered and their frequency
- RPS calculations and peak load analysis
- Application type identification (OLTP/OLAP/Mixed)
- Read/write ratio analysis
- DynamoDB readiness assessment

**After Schema Analysis**: 🔴 **REQUIRED** - You MUST provide insights on:
- Database structure and entity relationships
- Data distribution and table sizes
- Foreign key dependencies and constraints
- DynamoDB suitability assessment
- Potential design challenges

**After Traffic Analysis**: 🔴 **REQUIRED** - You MUST provide insights on:
- Activity timeline and usage patterns
- Load distribution across time periods
- Scalability assessment and bottlenecks
- Cost implications for DynamoDB data modeling
- Performance optimization opportunities

### Final Output:

Create `source_database_analysis.md` file with comprehensive analysis results using the template structure below.

## SOURCE DATABASE REQUIREMENTS FILE TEMPLATE
```markdown
# Source Database Analysis Results

## Analysis Metadata
- **Analysis Date**: [CURRENT_TIMESTAMP]
- **Source Database Type**: [SOURCE_DB_TYPE]
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

## DynamoDB Data Modeling Considerations

### ❌ Unsupported Features (Require Application Changes)
| Feature Type | Count | Names | Required Action |
|--------------|-------|-------|-----------------|
| Stored Procedures | [count] | [list names or 'None'] | Move logic to application/Lambda |
| Triggers | [count] | [list names or 'None'] | Implement in application/Lambda |
| Functions | [count] | [list names or 'None'] | Move logic to application/Lambda |
| Auto-increment Columns | [count] | [list columns or 'None'] | Generate IDs in application (UUIDs) |
| Unique Constraints | [count] | [list constraints or 'None'] | Implement validation in application |
| Check Constraints | [count] | [list constraints or 'None'] | Implement validation in application |
| Default Values | [count] | [list columns or 'None'] | Set defaults in application code |

### 🔄 Features Requiring DynamoDB Redesign (Handled by Data Modeling)
| Feature Type | Count | Examples | DynamoDB Solution |
|--------------|-------|----------|-------------------|
| Views | [count] | [list names or 'None'] | Access pattern redesign |
| Foreign Keys | [count] | [list relationships or 'None'] | Single-table design patterns |
| Complex JOINs | [detected in patterns] | [pattern examples] | Denormalization strategies |
| Multi-table Queries | [detected in patterns] | [pattern examples] | Item collections/GSI design |

### Data Modeling Complexity Assessment
- **Application Changes**: [count from first table] features require code changes
- **DynamoDB Redesign**: [count from second table] features require data modeling
- **Overall Complexity**: Low/Medium/High based on total feature count

**Next Steps**:
- Application features → Plan development work for unsupported features
- DynamoDB features → Continue to data modeling workflow for design solutions

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
| Pattern # | Original Query (Normalized) | Frequency | RPS | Complexity Type | Index Usage |
|-----------|---------------------|-----------|-----|-------|-----------------|-------------|
[List all discovered patterns with metrics from integrated complexity analysis]

### High Frequency Patterns (>1.0 RPS)
[For each high-frequency pattern, include:]
- **Original SQL**: `[exact query from database logs]`
- **Frequency**: [count] queries over [ANALYSIS_DAYS] Days
- **Calculated RPS**: [frequency / time_period_seconds]
- **Unique Users**: [count of distinct user values]
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
- **Query Log Coverage**: [based on database log availability and time period]
- **Pattern Detection Method**: Automated from database performance logs with integrated complexity classification
- **RPS Calculation**: Query frequency divided by analysis period seconds
- **Schema Source**: Database system tables with relationship analysis
- **Confidence Level**: [High/Medium/Low based on data completeness and pattern count]

### Limitations
- **Sample Period**: [actual period that provided sufficient meaningful patterns]
- **Missing Patterns**: [potential patterns not captured in logs during analysis period]
- **System Queries**: Excluded from analysis with comprehensive filtering
- **Complexity Classification**: Based on SQL structure analysis for DynamoDB data modeling planning

### DynamoDB Data Modeling Considerations
- **Foreign Key Dependencies**: [count] relationships detected requiring DynamoDB design consideration
- **Complex Queries**: [count] JOIN/Complex patterns requiring access pattern redesign
- **Data Volume**: [total_size_mb] MB total database size suitable for DynamoDB data modeling

## Next Steps
1. Review patterns for accuracy and business context
2. Use `dynamodb_data_modeling` tool with this analysis
3. The modeling tool will use this source database analysis as input and gather additional requirements if needed
```
