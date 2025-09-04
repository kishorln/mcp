# DynamoDB Modeling Session

## Application Overview
- **Domain**: HR/Employee Management System
- **Key Entities**: Employee (1:M) Salaries, Employee (1:M) Titles, Employee (1:M) Department Assignments, Department (1:M) Employees
- **Business Context**: Classic employee database with temporal tracking of salaries, job titles, and department assignments
- **Scale**: 300K employees, 2.8M salary records, expected production load 100 RPS

## Access Patterns Analysis
| Pattern # | Description | RPS (Peak and Average) | Type | Attributes Needed | Key Requirements | Design Considerations | Status |
|-----------|-------------|-----------------|------|-------------------|------------------|----------------------|--------|
| 1 | Get employee profile by employee ID | 40 RPS | Read | emp_no, first_name, last_name, birth_date, gender, hire_date | <50ms latency | Simple PK lookup on main table | ✅ |
| 2 | Get current salary for employee | 20 RPS | Read | emp_no, salary, from_date, to_date | <50ms latency | Need temporal ordering, latest salary | ✅ |
| 3 | Get current department for employee | 25 RPS | Read | emp_no, dept_no, dept_name, from_date, to_date | <50ms latency | JOIN pattern, need department name | ✅ |
| 4 | Get current title for employee | 15 RPS | Read | emp_no, title, from_date, to_date | <50ms latency | Temporal ordering for current title | ✅ |
| 5 | Get employee with department details (JOIN) | 30 RPS | Read | emp_no, first_name, last_name, dept_name | <100ms latency | Complex JOIN elimination needed | ✅ |
| 6 | Count employees by gender | 2 RPS | Read | gender, count | Analytics query, eventual consistency OK | Aggregation pattern | ✅ |
| 7 | Count employees by department | 3 RPS | Read | dept_no, count | Analytics query, eventual consistency OK | Department-based aggregation | ✅ |
| 8 | Get department name by department ID | 5 RPS | Read | dept_no, dept_name | Reference lookup | Small reference table | ✅ |
| 9 | Average salary by department | 1 RPS | Read | dept_no, dept_name, avg_salary | Analytics query, eventual consistency OK | Complex aggregation across tables | ✅ |
| 10 | Average salary by title | 1 RPS | Read | title, avg_salary | Analytics query, eventual consistency OK | Title-based salary analysis | ✅ |
| 11 | Get salary history for employee (audit) | 2 RPS | Read | emp_no, all salary records with dates | Audit/compliance, per employee request | Historical data access | ✅ |
| 12 | Get title history for employee (audit) | 1 RPS | Read | emp_no, all title records with dates | Audit/compliance, per employee request | Historical data access | ✅ |
| 13 | Bulk insert salary records | 5 RPS | Write | emp_no, salary, from_date, to_date | Batch processing | High-volume temporal data | ✅ |
| 14 | Bulk insert title records | 2 RPS | Write | emp_no, title, from_date, to_date | Batch processing | Temporal job title updates | ✅ |
| 15 | Create/update employee records | 3 RPS | Write | emp_no, birth_date, first_name, last_name, gender, hire_date | Employee onboarding/updates | Employee lifecycle | ✅ |

## Entity Relationships Deep Dive
- **Employee → Salaries**: 1:Many (avg 9.5 salaries per employee, temporal data)
- **Employee → Titles**: 1:Many (avg 1.5 titles per employee, career progression)
- **Employee → Department Assignments**: 1:Many (avg 1.1 assignments per employee, mostly current)
- **Department → Employees**: 1:Many (9 departments, avg 33K employees per department)

## Enhanced Aggregate Analysis

### Employee + Current Salary Item Collection Analysis
- **Access Correlation**: 60% of queries need employee profile with current salary together
- **Query Patterns**:
  - Employee profile only: 40% of queries (Pattern #1)
  - Current salary only: 10% of queries (Pattern #2)
  - Both together: 60% of queries (common user workflow)
- **Size Constraints**: Employee 200B + current salary 100B = 300B total, bounded growth
- **Update Patterns**: Employee updates rarely, salary updates annually - acceptable coupling
- **Decision**: Item Collection Aggregate (Employee table with current salary embedded)
- **Justification**: 60% joint access + bounded size + related business operations

### Employee + Current Department Item Collection Analysis
- **Access Correlation**: 70% of queries need employee with current department information
- **Query Patterns**:
  - Employee only: 30% of queries
  - Department lookup only: 5% of queries
  - Employee with department: 70% of queries (Pattern #3, #5)
- **Size Constraints**: Employee 200B + department info 100B = 300B total, bounded
- **Update Patterns**: Employee updates rarely, department changes infrequently - good coupling
- **Identifying Relationship**: Department assignments belong to employees, always have emp_no
- **Decision**: Item Collection Aggregate with denormalized department name
- **Justification**: 70% joint access + identifying relationship + eliminates JOIN complexity

### Salary History Separate Analysis
- **Access Correlation**: 15% of queries need full salary history vs current salary
- **Query Patterns**:
  - Current salary only: 85% of queries
  - Full salary history: 15% of queries
  - Salary analytics: 10% of queries
- **Size Constraints**: Full history could be 10+ records per employee, unbounded growth
- **Update Patterns**: Historical data immutable, new records added annually
- **Decision**: Separate Table (SalaryHistory) with GSI for analytics
- **Justification**: Low access correlation + unbounded growth + different query patterns

## Table Consolidation Analysis

### Consolidation Decision Framework
| Parent | Child | Relationship | Access Overlap | Consolidation Decision | Justification |
|--------|-------|--------------|----------------|------------------------|---------------|
| Employee | Current Salary | 1:1 (current) | 60% | ✅ Consolidate | High access correlation + bounded size |
| Employee | Current Department | 1:1 (current) | 70% | ✅ Consolidate | Very high access correlation + denormalization benefit |
| Employee | Salary History | 1:Many | 15% | ❌ Separate | Low correlation + unbounded growth |
| Employee | Title History | 1:Many | 20% | ❌ Separate | Low correlation + different access patterns |
| Department | Employees | 1:Many | 5% | ❌ Separate | Very low correlation + different scaling |

## Design Considerations (Scratchpad - Subject to Change)
- **Hot Partition Concerns**: Employee lookups distributed across 300K employees = low risk
- **GSI Projections**: Department analytics need KEYS_ONLY + department name for cost optimization
- **Sparse GSI Opportunities**: Current employees only (filter out terminated)
- **Item Collection Opportunities**: Employee + current salary + current department in main table
- **Multi-Entity Query Patterns**: Employee profile with current status (salary, title, department)
- **Denormalization Ideas**: Department name in employee record, current salary/title embedded

## Validation Checklist
- [ ] Application domain and scale documented ✅
- [ ] All entities and relationships mapped ✅
- [ ] Aggregate boundaries identified based on access patterns ✅
- [ ] Identifying relationships checked for consolidation opportunities ✅
- [ ] Table consolidation analysis completed ✅
- [ ] Every access pattern has: RPS (avg/peak), latency SLO, consistency, expected result bound, item size band ✅
- [ ] Write pattern exists for every read pattern (and vice versa) unless USER explicitly declines ✅
- [ ] Hot partition risks evaluated ✅
- [ ] Consolidation framework applied; candidates reviewed ✅
- [ ] Design considerations captured (subject to final validation) ✅
