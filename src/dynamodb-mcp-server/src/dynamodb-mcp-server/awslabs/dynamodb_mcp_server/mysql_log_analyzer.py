"""MySQL General Log File Analysis Module for DynamoDB Migration"""

import re
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict


def parse_mysql_log_file(file_path: str) -> List[Dict[str, Any]]:
    """Parse MySQL general log file with dynamic format detection"""
    queries = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
        if not lines:
            return []
        
        # Check if first line looks like CSV headers
        first_line = lines[0].strip()
        if any(header in first_line.upper() for header in ['EVENT_TIME', 'ARGUMENT', 'COMMAND_TYPE', 'USER_HOST']):
            return _parse_csv_extract(lines)
        
        # Otherwise parse as standard general log format
        return _parse_standard_log(lines)


def _parse_csv_extract(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse CSV extract from mysql.general_log table"""
    queries = []
    
    # Parse header to find column indices
    header = lines[0].strip()
    delimiter = ',' if ',' in header else '\t'
    columns = [col.strip().strip('"\'') for col in header.split(delimiter)]
    
    # Find required column indices (case insensitive)
    col_map = {col.upper(): i for i, col in enumerate(columns)}
    
    # Look for timestamp columns
    time_idx = None
    for time_col in ['EVENT_TIME', 'TIMESTAMP', 'TIME']:
        if time_col in col_map:
            time_idx = col_map[time_col]
            break
    
    # Look for query/argument columns  
    query_idx = None
    for query_col in ['ARGUMENT', 'QUERY', 'SQL_TEXT']:
        if query_col in col_map:
            query_idx = col_map[query_col]
            break
    
    # Look for command columns
    command_idx = col_map.get('COMMAND_TYPE', col_map.get('COMMAND'))
    
    # Look for connection columns
    conn_idx = col_map.get('CONNECTION_ID', col_map.get('THREAD_ID'))
    
    if time_idx is None or query_idx is None:
        return []  # Missing required columns
    
    # Parse data rows
    for line in lines[1:]:
        if not line.strip():
            continue
            
        parts = line.strip().split(delimiter)
        if len(parts) < len(columns):
            continue
        
        try:
            timestamp_str = parts[time_idx].strip('"\'')
            query_text = parts[query_idx].strip('"\'')
            command = parts[command_idx].strip('"\'') if command_idx is not None else 'Query'
            connection_id = parts[conn_idx].strip('"\'') if conn_idx is not None else '0'
            
            # Decode hex-encoded query if needed
            if query_text.startswith('0x') or query_text.startswith('0X'):
                try:
                    # Remove 0x prefix and decode hex to bytes, then to string
                    hex_data = query_text[2:]
                    query_bytes = bytes.fromhex(hex_data)
                    query_text = query_bytes.decode('utf-8', errors='ignore')
                except:
                    # If hex decoding fails, use original text
                    pass
            
            # Skip system queries
            if _is_system_query(query_text):
                continue
            
            # Parse timestamp
            try:
                if 'T' in timestamp_str:
                    ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    ts = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except:
                ts = datetime.now()
            
            queries.append({
                'timestamp': ts,
                'connection_id': connection_id,
                'command': command,
                'query': query_text
            })
            
        except (ValueError, IndexError):
            continue
    
    return queries


def _parse_standard_log(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse standard MySQL general log format"""
    queries = []
    
    # Try to detect delimiter and structure from sample lines
    sample_lines = [line.strip() for line in lines[:20] if line.strip() and not line.startswith('#')]
    
    if not sample_lines:
        return []
    
    # Detect delimiter (tab, comma, or multiple spaces)
    delimiter = None
    for line in sample_lines:
        if '\t' in line and len(line.split('\t')) >= 4:
            delimiter = '\t'
            break
        elif ',' in line and len(line.split(',')) >= 4:
            delimiter = ','
            break
        elif len(line.split()) >= 4:
            delimiter = None  # Space-separated
            break
    
    if delimiter is None and not any(len(line.split()) >= 4 for line in sample_lines):
        return []
    
    # Parse each line
    current_query = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Split by delimiter
        if delimiter:
            parts = line.split(delimiter)
        else:
            parts = line.split()
        
        if len(parts) >= 4:
            # Extract: timestamp, connection_id, command, query
            timestamp_str = parts[0].strip('"\'')
            connection_id = parts[1]
            command = parts[2]
            query = delimiter.join(parts[3:]) if delimiter else ' '.join(parts[3:])
            
            # Save previous query if exists
            if current_query and not _is_system_query(current_query['query']):
                queries.append(current_query)
            
            if command in ['Query', 'Execute', 'Prepare']:
                # Parse timestamp flexibly
                try:
                    if 'T' in timestamp_str and timestamp_str.endswith('Z'):
                        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    elif '-' in timestamp_str and ':' in timestamp_str:
                        # Try common formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%m/%d/%Y %H:%M:%S']:
                            try:
                                ts = datetime.strptime(timestamp_str, fmt)
                                break
                            except:
                                continue
                        else:
                            ts = datetime.now()  # Fallback
                    else:
                        ts = datetime.now()  # Fallback
                except:
                    ts = datetime.now()  # Fallback
                
                current_query = {
                    'timestamp': ts,
                    'connection_id': connection_id,
                    'command': command,
                    'query': query.strip()
                }
            else:
                current_query = None
        else:
            # Continue multi-line query
            if current_query and line.strip():
                current_query['query'] += ' ' + line.strip()
    
    # Don't forget the last query
    if current_query and not _is_system_query(current_query['query']):
        queries.append(current_query)

    return queries


def analyze_query_patterns(queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze query patterns and auto-calculate analysis period"""
    if not queries:
        return []
    
    # Auto-calculate analysis period from log timestamps
    timestamps = [q['timestamp'] for q in queries]
    time_span = max(timestamps) - min(timestamps)
    analysis_days = max(1, time_span.days + 1)  # At least 1 day
    
    pattern_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'frequency': 0, 'queries': [], 'first_seen': None, 'last_seen': None
    })
    
    for query_data in queries:
        # Normalize query to pattern
        pattern = _normalize_query(query_data['query'])
        
        stats = pattern_stats[pattern]
        stats['frequency'] += 1
        stats['queries'].append(query_data)
        
        # Track time range
        if stats['first_seen'] is None or query_data['timestamp'] < stats['first_seen']:
            stats['first_seen'] = query_data['timestamp']
        if stats['last_seen'] is None or query_data['timestamp'] > stats['last_seen']:
            stats['last_seen'] = query_data['timestamp']
    
    # Convert to results
    results = []
    total_duration = analysis_days * 24 * 3600
    
    for pattern, stats in pattern_stats.items():
        if stats['frequency'] > 0:  # Include all patterns with any frequency
            results.append({
                'query_pattern': pattern,
                'frequency': stats['frequency'],
                'calculated_rps': round(stats['frequency'] / total_duration, 4),
                'complexity_type': _classify_complexity(pattern),
                'index_usage_hint': _analyze_index_usage(pattern),
                'sample_query': stats['queries'][0]['query'][:200] + '...' if len(stats['queries'][0]['query']) > 200 else stats['queries'][0]['query']
            })
    
    return sorted(results, key=lambda x: x['frequency'], reverse=True)


def _is_system_query(query: str) -> bool:
    """Filter out system/administrative queries"""
    query_upper = query.upper().strip()
    
    # Filter out empty/blank queries
    if not query_upper or query_upper == '':
        return True
    
    # Prefix patterns (must start with these)
    prefix_patterns = [
        'SELECT @@', 'SET GLOBAL', 'SET SESSION', 'SET LOCAL', 'SET @@', 'SET ',
        'SHOW ', 'DESCRIBE ', 'EXPLAIN ', 'USE ', 'COMMIT', 'ROLLBACK',
        'START TRANSACTION', 'BEGIN', '/* RDS DATA API */', 'ALTER USER'
    ]
    
    # Keyword patterns (anywhere in query)
    keyword_patterns = [
        'INFORMATION_SCHEMA', 'PERFORMANCE_SCHEMA', 'MYSQL.', 'SYS.',
        'DIGEST_TEXT', 'EVENTS_STATEMENTS_', '@@GLOBAL', '@@SESSION',
        'OSCAR_LOCAL_ONLY_REPLICA_HOST_STATUS', 'SQL_LOG_BIN', 'CHARACTER_SET_RESULTS',
        'AUTOCOMMIT', 'SQL_MODE', 'RDSADMIN@'
    ]
    
    # Exact match patterns
    exact_patterns = [
        'SELECT 1', 'COMMIT', 'ROLLBACK'
    ]
    
    # Check exact patterns first
    if query_upper in exact_patterns:
        return True
    
    # Check prefix patterns
    if any(query_upper.startswith(pattern) for pattern in prefix_patterns):
        return True
    
    # Check keyword patterns
    if any(keyword in query_upper for keyword in keyword_patterns):
        return True
    
    return False


def _normalize_query(query: str) -> str:
    """Normalize query to pattern for grouping"""
    # Remove extra whitespace
    normalized = ' '.join(query.split())
    
    # Replace literals with placeholders
    normalized = re.sub(r"'[^']*'", "'?'", normalized)
    normalized = re.sub(r'"[^"]*"', '"?"', normalized)
    normalized = re.sub(r'\b\d+\b', '?', normalized)
    
    return normalized


def _classify_complexity(query: str) -> str:
    """Classify query complexity for DynamoDB migration planning"""
    query_upper = query.upper()
    
    if 'JOIN' in query_upper:
        if any(keyword in query_upper for keyword in ['GROUP BY', 'ORDER BY', 'HAVING']):
            return 'Complex JOIN'
        return 'JOIN Query'
    elif any(keyword in query_upper for keyword in ['WHERE', '=']):
        return 'Single Table Search'
    elif query_upper.startswith('SELECT'):
        return 'Simple SELECT'
    elif query_upper.startswith('INSERT'):
        return 'INSERT Operation'
    elif query_upper.startswith('UPDATE'):
        return 'UPDATE Operation'
    elif query_upper.startswith('DELETE'):
        return 'DELETE Operation'
    else:
        return 'Other'


def extract_table_names_from_patterns(patterns: List[Dict[str, Any]]) -> set:
    """Extract table names referenced in query patterns"""
    table_names = set()
    
    for pattern in patterns:
        query = pattern['sample_query'].upper()
        
        # Simple table name extraction from SQL
        # Look for FROM, JOIN, UPDATE, INSERT INTO patterns
        import re
        
        # FROM table_name
        from_matches = re.findall(r'FROM\s+(\w+)', query)
        table_names.update(from_matches)
        
        # JOIN table_name
        join_matches = re.findall(r'JOIN\s+(\w+)', query)
        table_names.update(join_matches)
        
        # UPDATE table_name
        update_matches = re.findall(r'UPDATE\s+(\w+)', query)
        table_names.update(update_matches)
        
        # INSERT INTO table_name
        insert_matches = re.findall(r'INSERT\s+INTO\s+(\w+)', query)
        table_names.update(insert_matches)
    
    # Filter out common SQL keywords that might be matched
    sql_keywords = {'SELECT', 'WHERE', 'ORDER', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET'}
    table_names = {name.lower() for name in table_names if name not in sql_keywords}
    
    return table_names


def _analyze_index_usage(query: str) -> str:
    """Analyze potential index usage for DynamoDB design"""
    query_upper = query.upper()
    
    if 'WHERE' in query_upper and '=' in query_upper:
        if 'ID' in query_upper:
            return 'Likely Primary Key'
        return 'Likely Indexed'
    elif 'WHERE' in query_upper and 'LIKE' in query_upper:
        return 'Potential Full Scan'
    elif 'ORDER BY' in query_upper:
        return 'Sort Key Candidate'
    else:
        return 'Unknown Index Usage'
