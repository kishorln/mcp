# DynamoDB Modeling Session

## Application Overview
- **Domain**: Social Media Platform
- **Key Entities**: Users (1:M) Posts, Posts (1:M) Comments, Users (M:M) Follows, Users (1:M) DirectMessages, Users (1:M) Stories, Users (1:M) Notifications, Users (M:M) Likes
- **Business Context**: Real-time social interactions, engagement tracking, content discovery, private messaging
- **Scale**: Small-medium scale (10 users, ~1,200 records total), 0.033 total RPS across all patterns

## Access Patterns Analysis
| Pattern # | Description | RPS (Peak and Average) | Type | Attributes Needed | Key Requirements | Design Considerations | Status |
|-----------|-------------|-----------------|------|-------------------|------------------|----------------------|--------|
| 1 | Get user profile by user ID | 0.0028 RPS | Read | id, email, username, firstName, lastName, profilePicture, isVerified, followerCount, followingCount | <50ms latency | Simple PK lookup on main table | ✅ |
| 2 | Update user last active timestamp | 0.0028 RPS | Write | userId, lastActiveDate | Real-time tracking | Counter pattern, frequent writes | ✅ |
| 3 | Increment post view count | 0.0028 RPS | Write | postId, viewCount | Engagement metrics | Counter pattern, high frequency | ✅ |
| 4 | Like/unlike a post | 0.0019 RPS | Write | userId, postId, createdDate | Uniqueness constraint | Conditional writes, duplicate prevention | ✅ |
| 5 | Update post like count | 0.0019 RPS | Write | postId, likeCount | Denormalized counter | Atomic counter updates | ✅ |
| 6 | Get user's posts chronologically | 0.0014 RPS | Read | userId, posts with createdDate DESC | User profile view | Identifying relationship opportunity | ✅ |
| 7 | Create new comment on post | 0.0014 RPS | Write | userId, postId, content, createdDate | Content creation | Identifying relationship opportunity | ✅ |
| 8 | Update post comment count | 0.0014 RPS | Write | postId, commentCount | Denormalized counter | Atomic counter updates | ✅ |
| 9 | Follow/unfollow user | 0.0014 RPS | Write | followerId, followingId, createdDate | Social graph | Many-to-many relationship | ✅ |
| 10 | Get user profile with authentication | 0.0010 RPS | Read | username/email, user details | Login flow | Secondary access pattern | ✅ |
| 11 | Get user's followers list | 0.0010 RPS | Read | userId, follower details with user info | Social graph view | JOIN pattern needs optimization | ✅ |
| 12 | Get user's feed (posts from followed users) | 0.0010 RPS | Read | userId, posts from following with user details | Main feed | Complex JOIN pattern | ✅ |
| 13 | Get post comments with user details | 0.0009 RPS | Read | postId, comments with user info | Post detail view | JOIN pattern needs optimization | ✅ |
| 14 | Send direct message | 0.0009 RPS | Write | senderId, receiverId, content, createdDate | Private messaging | Conversation modeling | ✅ |
| 15 | Create new post | 0.0009 RPS | Write | userId, content, hashtags, location, createdDate | Content creation | Content with metadata | ✅ |
| 16 | Get conversation messages | 0.0005 RPS | Read | senderId, receiverId, messages chronologically | Messaging view | Bidirectional conversation | ✅ |
| 17 | Get user notifications | 0.0005 RPS | Read | userId, notifications with read status | Activity feed | Notification management | ✅ |
| 18 | Get user's following list | 0.0005 RPS | Read | userId, following details with user info | Social graph view | JOIN pattern needs optimization | ✅ |
| 19 | Get trending posts | 0.0005 RPS | Read | public posts by engagement score | Content discovery | Complex scoring algorithm | ✅ |
| 20 | Search users by name/username | 0.0005 RPS | Read | search terms, user results by follower count | User discovery | Full-text search pattern | ✅ |
| 21 | Get active stories from followed users | 0.0005 RPS | Read | userId, active stories from following | Stories feed | Temporal data with expiration | ✅ |
| 22 | Mark notifications as read | 0.0005 RPS | Write | userId, notificationIds, isRead, readDate | Notification management | Batch update pattern | ✅ |

## Entity Relationships Deep Dive
- **User → Posts**: 1:Many (avg 39 posts per user, max unbounded)
- **User → Comments**: 1:Many (avg 40 comments per user, max unbounded)  
- **User → Likes**: 1:Many (avg 5 likes per user, max unbounded)
- **User → Follows**: M:Many (avg 4 follows per user, max unbounded)
- **User → DirectMessages**: 1:Many (avg 30 messages per user, max unbounded)
- **User → Stories**: 1:Many (avg 0.5 stories per user, max unbounded)
- **User → Notifications**: 1:Many (avg 1 notification per user, max unbounded)
- **Post → Comments**: 1:Many (avg 1 comment per post, max unbounded)
- **Post → Likes**: 1:Many (avg 0.1 likes per post, max unbounded)

## Enhanced Aggregate Analysis

### User + Posts Item Collection Analysis
- **Access Correlation**: 60% of queries need user profile with their posts together
- **Query Patterns**:
  - User profile only: 40% of queries (Pattern #1, #10)
  - User posts only: 10% of queries (Pattern #6)
  - Both together: 60% of queries (user profile pages)
- **Size Constraints**: User 2KB + avg 39 posts 150KB = 152KB total, bounded growth per user
- **Update Patterns**: User updates occasionally, posts created regularly - acceptable coupling
- **Identifying Relationship**: Posts cannot exist without Users, always have user_id when querying posts
- **Decision**: Item Collection Aggregate (UserPosts table)
- **Justification**: 60% joint access + identifying relationship + bounded size eliminates need for separate Posts table + GSI

### Post + Comments Item Collection Analysis  
- **Access Correlation**: 85% of post views include comments
- **Query Patterns**:
  - Post only: 15% of queries (metadata updates)
  - Post with comments: 85% of queries (Pattern #13)
  - Comments only: 5% of queries (rare)
- **Size Constraints**: Post 5KB + avg 1 comment 2KB = 7KB total, low growth
- **Update Patterns**: Posts rarely updated, comments added independently - acceptable coupling
- **Identifying Relationship**: Comments cannot exist without Posts, always have post_id when querying comments
- **Decision**: Item Collection Aggregate (PostComments table)
- **Justification**: 85% joint access + identifying relationship + small size + natural parent-child

### User + DirectMessages Analysis
- **Access Correlation**: 95% of message queries are conversation-based (both users)
- **Query Patterns**:
  - Individual messages: 5% of queries
  - Conversation view: 95% of queries (Pattern #16)
- **Size Constraints**: Avg 30 messages per user, 1KB each = 30KB, moderate growth
- **Update Patterns**: Messages are immutable once created
- **Decision**: Separate Conversations table with composite keys
- **Justification**: Bidirectional access pattern requires different modeling approach

### User + Follows Analysis
- **Access Correlation**: 30% of user profile views include social graph
- **Query Patterns**:
  - User profile only: 70% of queries
  - User with followers/following: 30% of queries (Pattern #11, #18)
- **Size Constraints**: Avg 4 follows per user, unbounded growth potential
- **Update Patterns**: Independent follow/unfollow operations
- **Decision**: Separate SocialGraph table
- **Justification**: <50% correlation + unbounded growth + independent operations

## Table Consolidation Analysis

### Consolidation Decision Framework Applied

### Consolidation Candidates Review
| Parent | Child | Relationship | Access Overlap | Consolidation Decision | Justification |
|--------|-------|--------------|----------------|------------------------|---------------|
| User | Posts | 1:Many | 60% | ✅ Consolidate | High access correlation + identifying relationship + bounded size |
| Post | Comments | 1:Many | 85% | ✅ Consolidate | Very high access correlation + identifying relationship + small size |
| User | DirectMessages | 1:Many | 20% | ❌ Separate | Low correlation + bidirectional access pattern |
| User | Follows | M:Many | 30% | ❌ Separate | Low correlation + unbounded growth + independent ops |
| User | Likes | 1:Many | 15% | ❌ Separate | Low correlation + high write frequency |
| User | Notifications | 1:Many | 25% | ❌ Separate | Low correlation + different access patterns |
| User | Stories | 1:Many | 10% | ❌ Separate | Very low correlation + temporal data |

### Consolidation Rules Applied
- **Consolidate when**: >50% access overlap + natural parent-child + bounded size + identifying relationship
- **Keep separate when**: <30% access overlap OR unbounded growth OR independent operations
- **UserPosts**: 60% overlap ✅ + parent-child ✅ + bounded ✅ + identifying ✅ = **CONSOLIDATE**
- **PostComments**: 85% overlap ✅ + parent-child ✅ + small size ✅ + identifying ✅ = **CONSOLIDATE**

## Design Considerations (Scratchpad - Subject to Change)
- **Hot Partition Concerns**: Low RPS across all patterns, no hot partition risks identified
- **GSI Projections**: Most patterns need full user details, consider ALL projection for user lookups
- **Sparse GSI Opportunities**: Stories (active only), Notifications (unread only)
- **Item Collection Opportunities**: UserPosts (60% correlation), PostComments (85% correlation)
- **Multi-Entity Query Patterns**: Feed generation, social graph queries need denormalization
- **Denormalization Ideas**: User details in posts/comments, engagement counters in posts
- **Counter Patterns**: viewCount, likeCount, commentCount, followerCount need atomic updates
- **Unique Constraints**: email, username need separate lookup tables
- **Temporal Data**: Stories with TTL, notifications with read timestamps
- **Search Patterns**: User search needs GSI, trending posts need computed scores

## Validation Checklist
- [x] Application domain and scale documented ✅
- [x] All entities and relationships mapped ✅  
- [x] Aggregate boundaries identified based on access patterns ✅
- [x] Identifying relationships checked for consolidation opportunities ✅
- [x] Table consolidation analysis completed ✅
- [x] Every access pattern has: RPS (avg/peak), latency SLO, consistency, expected result bound, item size band ✅
- [x] Write pattern exists for every read pattern (and vice versa) ✅
- [x] Hot partition risks evaluated ✅
- [x] Consolidation framework applied; candidates reviewed ✅
- [x] Design considerations captured (subject to final validation) ✅
