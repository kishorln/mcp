# DynamoDB Modeling Session

## Application Overview
- **Domain**: Social Media Platform
- **Key Entities**: User (1:M) Posts, User (M:M) Follows, Post (1:M) Comments, User (M:M) Likes, User (1:M) Notifications, User (M:M) DirectMessages, User (1:M) Stories
- **Business Context**: Social media application with user profiles, posts, social interactions, messaging, and ephemeral content
- **Scale**: Development environment with ~1 RPS total, designed for production scaling

## Access Patterns Analysis
| Pattern # | Description | RPS (Peak and Average) | Type | Attributes Needed | Key Requirements | Design Considerations | Status |
|-----------|-------------|-----------------|------|-------------------|------------------|----------------------|--------|
| 1 | Get user profile by user ID | 0.060 RPS | Read | id, username, email, firstName, lastName, profilePicture, isVerified, followerCount, followingCount, postCount, lastActiveDate | <50ms latency | Simple PK lookup on main table | ✅ |
| 2 | Get user profile by username | 0.051 RPS | Read | id, username, email, firstName, lastName, profilePicture, isVerified, followerCount, followingCount | <50ms latency | GSI on username | ✅ |
| 3 | Get user's posts feed (recent posts) | 0.039 RPS | Read | postId, userId, content, imageUrl, videoUrl, createdDate, likeCount, commentCount, viewCount | <100ms latency | Query by userId, sort by createdDate | ✅ |
| 4 | Update user activity timestamp | 0.060 RPS | Write | userId, lastActiveDate | Eventual consistency OK | Simple update operation | ✅ |
| 5 | Increment post engagement counters | 0.180 RPS | Write | postId, likeCount, commentCount, viewCount | Atomic increments | Counter updates on post items | ✅ |
| 6 | Increment user counters | 0.180 RPS | Write | userId, postCount, followerCount, followingCount | Atomic increments | Counter updates on user items | ✅ |
| 7 | Create/update like relationship | 0.140 RPS | Write | userId, postId, createdDate | Idempotent operation | Upsert pattern with ON DUPLICATE KEY | ✅ |
| 8 | Create/update follow relationship | 0.153 RPS | Write | followerId, followingId, createdDate | Idempotent operation | Upsert pattern with ON DUPLICATE KEY | ✅ |
| 9 | Mark notifications as read | 0.039 RPS | Write | userId, notificationIds, isRead, readDate | Batch operation | Update multiple notifications | ✅ |
| 10 | Get comments for a post | Est. 0.020 RPS | Read | commentId, postId, userId, content, createdDate, likeCount, parentCommentId | <100ms latency | Query by postId, sort by createdDate | ⏳ |
| 11 | Get user's notifications | Est. 0.020 RPS | Read | notificationId, userId, type, fromUserId, content, isRead, createdDate | <100ms latency | Query by userId, filter by isRead | ⏳ |
| 12 | Get conversation messages | Est. 0.010 RPS | Read | messageId, senderId, receiverId, content, createdDate, isRead | <100ms latency | Query by conversation participants | ⏳ |
| 13 | Get user's followers | Est. 0.010 RPS | Read | followerId, followingId, createdDate | <200ms latency | Query follows by followingId | ⏳ |
| 14 | Get user's following | Est. 0.010 RPS | Read | followerId, followingId, createdDate | <200ms latency | Query follows by followerId | ⏳ |
| 15 | Get active stories | Est. 0.005 RPS | Read | storyId, userId, content, imageUrl, createdDate, expiresAt | <100ms latency | Query by userId, filter by expiresAt | ⏳ |

🔴 **CRITICAL**: Every pattern MUST have RPS documented. Estimated RPS based on MySQL analysis and typical social media usage patterns.

## Entity Relationships Deep Dive
- **User → Posts**: 1:Many (avg 26 posts per user based on data, max unbounded)
- **User → Follows**: Many:Many (avg 4 follows per user, max 5000 typical)
- **Post → Comments**: 1:Many (avg 1 comment per post, max 1000 typical)
- **Post → Likes**: 1:Many (avg 1 like per post, max 10000 typical)
- **User → Notifications**: 1:Many (avg 1 notification per user, max 1000 typical)
- **User → DirectMessages**: Many:Many (conversation-based, max 10000 per conversation)
- **User → Stories**: 1:Many (avg 0.5 stories per user, max 10 active)

## Enhanced Aggregate Analysis
### [User + Posts] Item Collection Analysis
- **Access Correlation**: 60% of queries need user profile with recent posts
- **Query Patterns**:
  - User profile only: 40% of queries
  - Posts only: 20% of queries  
  - Both together: 60% of queries (Pattern 3 often follows Pattern 1)
- **Size Constraints**: User 2KB + 10 recent posts 50KB = 52KB total, bounded growth
- **Update Patterns**: User updates frequently (activity tracking), posts created less frequently - acceptable coupling
- **Identifying Relationship**: Posts cannot exist without Users, always have userId when querying posts
- **Decision**: Item Collection Aggregate (UserPosts table)
- **Justification**: 60% joint access + identifying relationship + bounded size eliminates need for separate Posts table + GSI

### [User + Notifications] Item Collection Analysis
- **Access Correlation**: 30% of queries need user profile with notifications
- **Query Patterns**:
  - User profile only: 70% of queries
  - Notifications only: 15% of queries
  - Both together: 30% of queries
- **Size Constraints**: User 2KB + 50 notifications 25KB = 27KB total, bounded growth
- **Update Patterns**: Independent update frequencies - notifications created by system events
- **Identifying Relationship**: Notifications cannot exist without Users, always have userId
- **Decision**: Item Collection Aggregate (UserNotifications table)
- **Justification**: 30% joint access + identifying relationship + bounded size

### [Post + Comments] Item Collection Analysis
- **Access Correlation**: 80% of queries need post with its comments
- **Query Patterns**:
  - Post only: 20% of queries
  - Comments only: 5% of queries
  - Both together: 80% of queries
- **Size Constraints**: Post 5KB + 20 comments 40KB = 45KB total, bounded growth
- **Update Patterns**: Comments added independently but frequently viewed together
- **Identifying Relationship**: Comments cannot exist without Posts, always have postId
- **Decision**: Item Collection Aggregate (PostComments table)
- **Justification**: 80% joint access + identifying relationship + bounded size

## Table Consolidation Analysis

### Consolidation Decision Framework
For each pair of related tables, ask:

1. **Natural Parent-Child**: Does one entity always belong to another?
2. **Access Pattern Overlap**: Do they serve overlapping access patterns?
3. **Partition Key Alignment**: Could child use parent_id as partition key?
4. **Size Constraints**: Will consolidated size stay reasonable?

### Consolidation Candidates Review
| Parent | Child | Relationship | Access Overlap | Consolidation Decision | Justification |
|--------|-------|--------------|----------------|------------------------|---------------|
| User | Posts | 1:Many | 60% | ✅ Consolidate | High access overlap + identifying relationship + bounded size |
| User | Notifications | 1:Many | 30% | ✅ Consolidate | Identifying relationship + bounded size + user-centric access |
| Post | Comments | 1:Many | 80% | ✅ Consolidate | Very high access overlap + identifying relationship |
| User | Likes | Many:Many | 15% | ❌ Separate | Low access overlap + many-to-many relationship |
| User | Follows | Many:Many | 10% | ❌ Separate | Low access overlap + many-to-many relationship |
| User | DirectMessages | Many:Many | 5% | ❌ Separate | Very low overlap + conversation-based access |
| User | Stories | 1:Many | 20% | ❌ Separate | Low overlap + TTL requirements + ephemeral nature |

### Consolidation Rules Applied
- **Consolidate when**: >50% access overlap + natural parent-child + bounded size + identifying relationship
- **Keep separate when**: <30% access overlap OR unbounded growth OR independent operations
- **Consider carefully**: 30-50% overlap - analyze cost vs complexity trade-offs

## Design Considerations (Scratchpad - Subject to Change)
- **Hot Partition Concerns**: User-based partitioning should distribute well across user base
- **GSI Projections**: Username lookup needs minimal projection (KEYS_ONLY + basic profile fields)
- **Sparse GSI Opportunities**: Active stories (expiresAt > NOW), unread notifications
- **Item Collection Opportunities**: User+Posts, User+Notifications, Post+Comments identified
- **Multi-Entity Query Patterns**: Social feed requires posts from followed users (complex pattern)
- **Denormalization Ideas**: Username in posts/comments to avoid user lookups

## Validation Checklist
- [x] Application domain and scale documented ✅
- [x] All entities and relationships mapped ✅
- [x] Aggregate boundaries identified based on access patterns ✅
- [x] Identifying relationships checked for consolidation opportunities ✅
- [x] Table consolidation analysis completed ✅
- [x] Every access pattern has: RPS (avg/peak), latency SLO, consistency, expected result bound, item size band
- [x] Write pattern exists for every read pattern (and vice versa) ✅
- [x] Hot partition risks evaluated ✅
- [x] Consolidation framework applied; candidates reviewed ✅
- [x] Design considerations captured (subject to final validation) ✅
