# MySQL Database Analysis Results

## Analysis Metadata
- **Analysis Date**: 2025-08-27T15:58:42.920Z
- **Source Database**: migration
- **Analysis Period**: 30 Days
- **Cross-Database Included**: FALSE (analysis focused on primary database)
- **Total Patterns Found**: 47
- **Analysis Step**: SUCCESSFUL (All 10 SQL templates completed)

## Database Schema Summary

### Tables Analyzed
| Table | Rows | Data Size (MB) | Index Size (MB) | Columns | Foreign Keys | Auto Increment | Created |
|-------|------|----------------|-----------------|---------|--------------|----------------|---------|
| posts | 266 | 0.08 | 0.06 | 14 | 1 | YES | 2025-08-05 16:20:27 |
| comments | 265 | 0.05 | 0.05 | 8 | 3 | YES | 2025-08-05 16:21:43 |
| direct_messages | 211 | 0.02 | 0.05 | 8 | 2 | YES | 2025-08-05 16:22:52 |
| likes | 48 | 0.02 | 0.05 | 4 | 2 | YES | 2025-08-05 16:21:15 |
| follows | 42 | 0.02 | 0.06 | 4 | 2 | YES | 2025-08-05 16:20:53 |
| notifications | 10 | 0.02 | 0.08 | 10 | 4 | YES | 2025-08-05 16:23:12 |
| users | 10 | 0.02 | 0.11 | 19 | 0 | YES | 2025-08-05 16:19:43 |
| stories | 5 | 0.02 | 0.05 | 9 | 1 | YES | 2025-08-05 16:22:19 |

### Database Objects Summary
| Object Type | Count | Names |
|-------------|-------|-------|
| Tables | 8 | comments,direct_messages,follows,likes,notifications,posts,stories,users |
| Triggers | 0 | None |

### Relationships Detected
#### Foreign Key Relationships
| Child Table | Child Column | Parent Table | Parent Column | Cardinality | Update Rule | Delete Rule |
|-------------|--------------|--------------|---------------|-------------|-------------|-------------|
| comments | parentCommentId | comments | id | 1:Many | NO ACTION | NO ACTION |
| comments | postId | posts | id | 1:Many | NO ACTION | NO ACTION |
| comments | userId | users | id | 1:Many | NO ACTION | NO ACTION |
| direct_messages | receiverId | users | id | 1:Many | NO ACTION | NO ACTION |
| direct_messages | senderId | users | id | 1:Many | NO ACTION | NO ACTION |
| follows | followerId | users | id | 1:1 or 1:0..1 | NO ACTION | NO ACTION |
| follows | followingId | users | id | 1:1 or 1:0..1 | NO ACTION | NO ACTION |
| likes | postId | posts | id | 1:1 or 1:0..1 | NO ACTION | NO ACTION |
| likes | userId | users | id | 1:1 or 1:0..1 | NO ACTION | NO ACTION |
| notifications | commentId | comments | id | 1:Many | NO ACTION | NO ACTION |
| notifications | fromUserId | users | id | 1:Many | NO ACTION | NO ACTION |
| notifications | postId | posts | id | 1:Many | NO ACTION | NO ACTION |
| notifications | userId | users | id | 1:Many | NO ACTION | NO ACTION |
| posts | userId | users | id | 1:Many | NO ACTION | NO ACTION |
| stories | userId | users | id | 1:Many | NO ACTION | NO ACTION |

## Access Patterns Discovered

### Pattern Summary
| Pattern # | Original MySQL Query | Frequency | RPS | Users | Complexity Type | Index Usage | First Seen | Last Seen |
|-----------|---------------------|-----------|-----|-------|-----------------|-------------|------------|-----------|
| 1 | UPDATE users SET postCount = postCount + 1 WHERE id = 1 | 155 | 0.060 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:22 | 2025-08-06 11:59:34 |
| 2 | SELECT * FROM users WHERE id = 2 | 155 | 0.060 | 1 | Single Table Search | Likely Primary Key | 2025-08-06 11:34:21 | 2025-08-06 11:59:33 |
| 3 | UPDATE posts SET likeCount = likeCount + 1 WHERE id = 3 | 155 | 0.060 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:22 | 2025-08-06 11:59:33 |
| 4 | UPDATE users SET lastActiveDate = NOW() WHERE id = 2 | 155 | 0.060 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:21 | 2025-08-06 11:59:33 |
| 5 | UPDATE posts SET viewCount = viewCount + 1 WHERE id = 2 | 153 | 0.059 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:24 | 2025-08-06 11:59:33 |
| 6 | SELECT id, username, email, firstName, lastName, profilePicture, isVerified, followerCount, followingCount FROM users WHERE username = 'sarahbrown' AND isActive = TRUE | 132 | 0.051 | 1 | Simple SELECT | Likely Indexed | 2025-08-06 11:31:57 | 2025-08-06 11:59:29 |
| 7 | UPDATE users SET followingCount = followingCount + 1 WHERE id = 3 | 101 | 0.039 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:23 | 2025-08-06 11:59:31 |
| 8 | SELECT * FROM users WHERE id = 4 | 101 | 0.039 | 1 | Single Table Search | Likely Primary Key | 2025-08-06 11:34:21 | 2025-08-06 11:59:29 |
| 9 | SELECT * FROM users WHERE id = 6 | 101 | 0.039 | 1 | Single Table Search | Likely Primary Key | 2025-08-06 11:34:21 | 2025-08-06 11:59:29 |
| 10 | SELECT * FROM posts WHERE userId = 2 ORDER BY createdDate DESC LIMIT 10 | 101 | 0.039 | 1 | Simple SELECT | Likely Primary Key | 2025-08-06 11:34:22 | 2025-08-06 11:59:30 |
| 11 | UPDATE notifications SET isRead = TRUE, readDate = NOW() WHERE userId = 2 AND id IN (1, 2, 3) | 101 | 0.039 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:23 | 2025-08-06 11:59:32 |
| 12 | UPDATE posts SET commentCount = commentCount + 1 WHERE id = 3 | 101 | 0.039 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:22 | 2025-08-06 11:59:31 |
| 13 | UPDATE posts SET likeCount = likeCount + 1 WHERE id = 1 | 101 | 0.039 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:22 | 2025-08-06 11:59:30 |
| 14 | UPDATE users SET lastActiveDate = NOW() WHERE id = 4 | 101 | 0.039 | 1 | Other | Likely Primary Key | 2025-08-06 11:34:21 | 2025-08-06 11:59:30 |
| 15 | INSERT INTO likes (userId, postId) VALUES (3, 4) ON DUPLICATE KEY UPDATE createdDate = NOW() | 101 | 0.039 | 1 | Other | Unknown Index Usage | 2025-08-06 11:34:22 | 2025-08-06 11:59:30 |

### High Frequency Patterns (>1.0 RPS)
None detected - all patterns are below 1.0 RPS

### Medium Frequency Patterns (0.01-1.0 RPS)
- **Pattern 1**: `UPDATE users SET postCount = postCount + 1 WHERE id = 1`
  - **Frequency**: 155 queries over 30 Days
  - **Calculated RPS**: 0.060
  - **Unique Users**: 1
  - **Complexity**: Other
  - **Index Usage**: Likely Primary Key
  - **Time Range**: 2025-08-06 11:34:22 to 2025-08-06 11:59:34

- **Pattern 2**: `SELECT * FROM users WHERE id = 2`
  - **Frequency**: 155 queries over 30 Days
  - **Calculated RPS**: 0.060
  - **Unique Users**: 1
  - **Complexity**: Single Table Search
  - **Index Usage**: Likely Primary Key
  - **Time Range**: 2025-08-06 11:34:21 to 2025-08-06 11:59:33

- **Pattern 6**: `SELECT id, username, email, firstName, lastName, profilePicture, isVerified, followerCount, followingCount FROM users WHERE username = 'sarahbrown' AND isActive = TRUE`
  - **Frequency**: 132 queries over 30 Days
  - **Calculated RPS**: 0.051
  - **Unique Users**: 1
  - **Complexity**: Simple SELECT
  - **Index Usage**: Likely Indexed
  - **Time Range**: 2025-08-06 11:31:57 to 2025-08-06 11:59:29

- **Pattern 10**: `SELECT * FROM posts WHERE userId = 2 ORDER BY createdDate DESC LIMIT 10`
  - **Frequency**: 101 queries over 30 Days
  - **Calculated RPS**: 0.039
  - **Unique Users**: 1
  - **Complexity**: Simple SELECT
  - **Index Usage**: Likely Primary Key
  - **Time Range**: 2025-08-06 11:34:22 to 2025-08-06 11:59:30

### Low Frequency Patterns (<0.01 RPS)
- **Pattern 32**: `select * from direct_messages`
  - **Frequency**: 2 queries over 30 Days
  - **Calculated RPS**: 0.0008
  - **Unique Users**: 1
  - **Complexity**: Full Table Scan
  - **Index Usage**: Unknown Index Usage
  - **Time Range**: 2025-08-05 16:39:25 to 2025-08-05 16:41:36

## Traffic Analysis

### Overall Statistics
- **Total RPS**: 0.9453 (calculated from all meaningful patterns)
- **Peak Hour**: Limited data - most activity concentrated in single day
- **Read/Write Ratio**: Approximately 30% reads, 70% writes (based on pattern analysis)
- **Unique Users**: 1 (test/development environment)
- **Analysis Period**: 30 days

### Database Scope
- **Primary Database Queries**: 100% (focused on migration database)
- **Cross-Database Queries**: 0% (no cross-database patterns detected)

### Data Volume Analysis
- **posts**: 266 records, 0.08 MB data, 0.06 MB indexes, 14 columns, 1 foreign key
- **comments**: 265 records, 0.05 MB data, 0.05 MB indexes, 8 columns, 3 foreign keys
- **direct_messages**: 211 records, 0.02 MB data, 0.05 MB indexes, 8 columns, 2 foreign keys
- **likes**: 48 records, 0.02 MB data, 0.05 MB indexes, 4 columns, 2 foreign keys
- **follows**: 42 records, 0.02 MB data, 0.06 MB indexes, 4 columns, 2 foreign keys
- **notifications**: 10 records, 0.02 MB data, 0.08 MB indexes, 10 columns, 4 foreign keys
- **users**: 10 records, 0.02 MB data, 0.11 MB indexes, 19 columns, 0 foreign keys
- **stories**: 5 records, 0.02 MB data, 0.05 MB indexes, 9 columns, 1 foreign key

## Cross-Database Analysis
No cross-database patterns detected. Analysis focused on: migration

## Technical Notes

### Analysis Quality
- **Query Log Coverage**: 30 days of general_log data with TABLE output enabled
- **Pattern Detection Method**: Automated from mysql.general_log with integrated complexity classification
- **RPS Calculation**: Query frequency divided by analysis period seconds (2,592,000 seconds for 30 days)
- **Schema Source**: information_schema tables with relationship analysis
- **Confidence Level**: HIGH (complete data set with all templates executed successfully)

### Limitations
- **Sample Period**: 30 days with most activity concentrated in single day (2025-08-06)
- **Missing Patterns**: Development/test environment may not represent production patterns
- **System Queries**: Excluded from analysis with comprehensive filtering
- **Complexity Classification**: Based on SQL structure analysis for DynamoDB migration planning

### Migration Considerations
- **Foreign Key Dependencies**: 15 relationships detected requiring DynamoDB design consideration
- **Complex Queries**: 0 JOIN/Complex patterns requiring access pattern redesign
- **Data Volume**: 0.23 MB total database size suitable for DynamoDB migration
- **Social Media Domain**: Typical social media access patterns with user profiles, posts, likes, follows, comments, and notifications

---
*Generated by MySQL Database Analyzer*
*Ready for DynamoDB Data Modeling Tool*

## Next Steps
1. Review patterns for accuracy and business context
2. Use `dynamodb_data_modeling` tool with this analysis
3. The modeling tool will use this MySQL analysis as input and gather additional requirements if needed
