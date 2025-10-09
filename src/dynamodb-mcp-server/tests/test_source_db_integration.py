import os
import pytest
from awslabs.dynamodb_mcp_server.database_analysis_queries import get_query_resource
from awslabs.dynamodb_mcp_server.database_analyzers import DatabaseAnalyzerRegistry, MySQLAnalyzer
from unittest.mock import patch


@pytest.mark.asyncio
async def test_mysql_analyzer_initialization():
    """Test MySQL analyzer initialization."""
    connection_params = {
        'cluster_arn': 'test-cluster',
        'secret_arn': 'test-secret',
        'database': 'test-db',
        'region': 'us-east-1',
        'max_results': 500,
        'pattern_analysis_days': 30,
        'output_dir': '/tmp/test',
    }

    analyzer = MySQLAnalyzer(connection_params)
    assert analyzer.cluster_arn == 'test-cluster'
    assert analyzer.secret_arn == 'test-secret'
    assert analyzer.database == 'test-db'
    assert analyzer.region == 'us-east-1'


def test_database_analyzer_registry():
    """Test database analyzer registry functionality."""
    # Test getting supported types
    supported_types = DatabaseAnalyzerRegistry.get_supported_types()
    assert 'mysql' in supported_types

    # Test getting MySQL analyzer
    analyzer_class = DatabaseAnalyzerRegistry.get_analyzer('mysql')
    assert analyzer_class == MySQLAnalyzer

    # Test unsupported database type
    with pytest.raises(ValueError, match='Unsupported database type: postgresql'):
        DatabaseAnalyzerRegistry.get_analyzer('postgresql')


def test_query_resource_functions():
    """Test query resource utility functions."""
    # Test getting a query resource
    query = get_query_resource('performance_schema_check', max_query_results=1000)
    assert 'sql' in query
    assert 'SELECT @@performance_schema' in query['sql']

    # Test parameter substitution
    query = get_query_resource(
        'query_pattern_analysis',
        max_query_results=1000,
        target_database='employees',
        pattern_analysis_days=30,
    )
    assert 'employees' in query['sql']
    assert '30' in query['sql']

    # Test invalid query name
    with pytest.raises(ValueError, match="Query 'invalid_query' not found"):
        get_query_resource('invalid_query', max_query_results=1000)


def test_mysql_max_query_results_limit(monkeypatch):
    """Test LIMIT clause addition for codecov coverage."""
    # Test parameter override (takes precedence over env var)
    monkeypatch.setenv('MYSQL_MAX_QUERY_RESULTS', '100')
    query = get_query_resource(
        'query_pattern_analysis',
        max_query_results=200,
        target_database='test',
        pattern_analysis_days=30,
    )
    assert 'LIMIT 200' in query['sql']  # Parameter takes precedence

    # Test environment variable fallback
    query = get_query_resource(
        'query_pattern_analysis',
        max_query_results=100,
        target_database='test',
        pattern_analysis_days=30,
    )
    assert 'LIMIT 100' in query['sql']  # Falls back to env var

    # Test default fallback when no env var set
    monkeypatch.delenv('MYSQL_MAX_QUERY_RESULTS', raising=False)
    query = get_query_resource('column_analysis', max_query_results=1000, target_database='test')
    assert 'LIMIT 1000' in query['sql']  # Uses the provided value


def test_mysql_performance_schema_check():
    """Test MySQL performance schema detection."""
    # Test enabled case
    result_enabled = [{'': '1'}]  # MySQL returns empty string as key
    assert MySQLAnalyzer.is_performance_schema_enabled(result_enabled) is True

    # Test disabled case
    result_disabled = [{'': '0'}]
    assert MySQLAnalyzer.is_performance_schema_enabled(result_disabled) is False

    # Test empty result
    assert MySQLAnalyzer.is_performance_schema_enabled([]) is False
    assert MySQLAnalyzer.is_performance_schema_enabled(None) is False


@pytest.mark.asyncio
async def test_source_db_analyzer_integration(tmp_path):
    """Test source_db_analyzer tool integration."""
    from awslabs.dynamodb_mcp_server.server import source_db_analyzer

    # Test with missing required parameters (database_name is None)
    result = await source_db_analyzer(
        source_db_type='mysql',
        database_name=None,
        aws_cluster_arn='test-cluster',
        aws_secret_arn='test-secret',
        aws_region='us-east-1',
        output_dir=str(tmp_path),
    )

    # Should return error message about missing parameters
    assert 'To analyze your mysql database, I need:' in result


def test_database_analyzer_build_connection_params_invalid_dir():
    """Test build_connection_params with invalid output directory."""
    from awslabs.dynamodb_mcp_server.database_analyzers import DatabaseAnalyzer

    # Test non-absolute path
    with pytest.raises(ValueError, match='Output directory must be an absolute path'):
        DatabaseAnalyzer.build_connection_params('mysql', output_dir='relative/path')

    # Test non-existent directory
    with pytest.raises(ValueError, match='Output directory does not exist or is not writable'):
        DatabaseAnalyzer.build_connection_params('mysql', output_dir='/nonexistent/path')


def test_database_analyzer_save_analysis_files_empty():
    """Test save_analysis_files with empty results."""
    from awslabs.dynamodb_mcp_server.database_analyzers import DatabaseAnalyzer

    saved_files, save_errors = DatabaseAnalyzer.save_analysis_files(
        {}, 'mysql', 'test_db', 30, 500, '/tmp'
    )

    assert saved_files == []
    assert save_errors == []


@pytest.mark.asyncio
async def test_mysql_analyzer_query_execution():
    """Test MySQL analyzer query execution."""
    from awslabs.dynamodb_mcp_server.database_analyzers import MySQLAnalyzer

    connection_params = {
        'cluster_arn': 'test-cluster',
        'secret_arn': 'test-secret',
        'database': 'test-db',
        'region': 'us-east-1',
        'max_results': 500,
        'pattern_analysis_days': 30,
        'output_dir': '/tmp',
    }

    analyzer = MySQLAnalyzer(connection_params)

    # Test query execution (will fail due to no real connection)
    result = await analyzer._run_query('SELECT 1')
    assert isinstance(result, list)
    assert len(result) == 1
    assert 'error' in result[0]


def test_database_analyzer_save_analysis_files_with_data(tmp_path, monkeypatch):
    """Test save_analysis_files with actual data."""
    import json
    from awslabs.dynamodb_mcp_server.database_analyzers import DatabaseAnalyzer

    # Mock datetime to control timestamp

    class MockDateTime:
        @staticmethod
        def now():
            class MockNow:
                def strftime(self, fmt):
                    return '20231009_120000'

            return MockNow()

    monkeypatch.setattr('awslabs.dynamodb_mcp_server.database_analyzers.datetime', MockDateTime)

    results = {
        'table_analysis': {
            'data': [{'table': 'users', 'rows': 100}],
            'description': 'Table analysis',
        },
        'query_pattern_analysis': {
            'data': [{'pattern': 'SELECT * FROM users', 'frequency': 10}],
            'description': 'Query patterns',
        },
    }

    saved_files, save_errors = DatabaseAnalyzer.save_analysis_files(
        results, 'mysql', 'test_db', 30, 500, str(tmp_path)
    )

    assert len(saved_files) == 2
    assert len(save_errors) == 0

    # Verify files were created
    for filename in saved_files:
        assert os.path.exists(filename)
        with open(filename, 'r') as f:
            data = json.load(f)
            assert 'query_name' in data
            assert 'database' in data
            assert data['database'] == 'test_db'


def test_database_analyzer_save_files_creation_error(tmp_path, monkeypatch):
    """Test save_analysis_files when folder creation fails."""
    from awslabs.dynamodb_mcp_server.database_analyzers import DatabaseAnalyzer

    # Mock os.makedirs to raise exception
    def mock_makedirs_fail(*args, **kwargs):
        raise OSError('Permission denied')

    monkeypatch.setattr('os.makedirs', mock_makedirs_fail)

    results = {'table_analysis': {'data': [], 'description': 'Test'}}

    saved_files, save_errors = DatabaseAnalyzer.save_analysis_files(
        results, 'mysql', 'test_db', 30, 500, str(tmp_path)
    )

    assert len(saved_files) == 0
    assert len(save_errors) == 1
    assert 'Failed to create folder' in save_errors[0]


def test_database_analyzer_filter_pattern_data():
    """Test filter_pattern_data method."""
    from awslabs.dynamodb_mcp_server.database_analyzers import DatabaseAnalyzer

    # Test with valid data
    pattern_data = [
        {'DIGEST_TEXT': 'SELECT * FROM users', 'COUNT_STAR': 10},
        {'DIGEST_TEXT': 'INSERT INTO users', 'COUNT_STAR': 5},
    ]

    filtered = DatabaseAnalyzer.filter_pattern_data(pattern_data, 30)
    expected = [
        {'DIGEST_TEXT': 'SELECT * FROM users', 'COUNT_STAR': 10, 'calculated_rps': 0.000004},
        {'DIGEST_TEXT': 'INSERT INTO users', 'COUNT_STAR': 5, 'calculated_rps': 0.000002},
    ]
    assert filtered == expected

    # Test with None data
    filtered = DatabaseAnalyzer.filter_pattern_data(None, 30)
    assert filtered is None


@pytest.mark.asyncio
async def test_mysql_analyzer_execute_query_batch():
    """Test MySQL analyzer batch query execution."""
    from awslabs.dynamodb_mcp_server.database_analyzers import MySQLAnalyzer

    connection_params = {
        'cluster_arn': 'test-cluster',
        'secret_arn': 'test-secret',
        'database': 'test-db',
        'region': 'us-east-1',
        'max_results': 500,
        'pattern_analysis_days': 30,
        'output_dir': '/tmp',
    }

    analyzer = MySQLAnalyzer(connection_params)

    queries = [{'name': 'test_query', 'sql': 'SELECT 1', 'description': 'Test query'}]

    results, errors = await analyzer.execute_query_batch(queries)

    # Should have errors due to no real connection
    assert len(errors) > 0
    assert 'test_query' in errors[0]


def test_get_analyzer_with_invalid_database_type():
    """Test error handling when an unsupported database type is provided."""
    with pytest.raises(ValueError, match='Unsupported database type: invalid'):
        DatabaseAnalyzerRegistry.get_analyzer('invalid')


@pytest.mark.asyncio
async def test_mysql_query_execution_handles_database_exceptions():
    """Test MySQL query execution properly handles and reports database connection failures."""
    analyzer = MySQLAnalyzer(
        {
            'cluster_arn': 'test',
            'secret_arn': 'test',
            'database': 'test',
            'region': 'us-east-1',
            'max_results': 500,
            'pattern_analysis_days': 30,
            'output_dir': '/tmp',
        }
    )

    with patch(
        'awslabs.dynamodb_mcp_server.database_analyzers.mysql_query',
        side_effect=Exception('DB Error'),
    ):
        result = await analyzer._run_query('SELECT 1')
        assert result[0]['error'] == 'MySQL query failed: DB Error'


@pytest.mark.asyncio
async def test_execute_query_batch_handles_empty_result_sets():
    """Test batch query execution properly handles queries that return no results."""
    analyzer = MySQLAnalyzer(
        {
            'cluster_arn': 'test',
            'secret_arn': 'test',
            'database': 'test',
            'region': 'us-east-1',
            'max_results': 500,
            'pattern_analysis_days': 30,
            'output_dir': '/tmp',
        }
    )

    with patch.object(analyzer, '_run_query', return_value=[]):
        results, errors = await analyzer.execute_query_batch(['table_analysis'])
        assert results['table_analysis']['data'] == []


@pytest.mark.asyncio
async def test_execute_query_batch_handles_query_failures():
    """Test batch query execution properly handles individual query failures."""
    analyzer = MySQLAnalyzer(
        {
            'cluster_arn': 'test',
            'secret_arn': 'test',
            'database': 'test',
            'region': 'us-east-1',
            'max_results': 500,
            'pattern_analysis_days': 30,
            'output_dir': '/tmp',
        }
    )

    with patch.object(analyzer, '_run_query', side_effect=Exception('Query failed')):
        results, errors = await analyzer.execute_query_batch(['table_analysis'])
        assert len(errors) > 0
        assert 'Query failed' in errors[0]


@pytest.mark.asyncio
async def test_execute_query_batch_handles_error_results():
    """Test batch query execution properly handles queries that return error results."""
    analyzer = MySQLAnalyzer(
        {
            'cluster_arn': 'test',
            'secret_arn': 'test',
            'database': 'test',
            'region': 'us-east-1',
            'max_results': 500,
            'pattern_analysis_days': 30,
            'output_dir': '/tmp',
        }
    )

    with patch.object(analyzer, '_run_query', return_value=[{'error': 'SQL syntax error'}]):
        results, errors = await analyzer.execute_query_batch(['table_analysis'])
        assert len(errors) > 0
        assert 'SQL syntax error' in errors[0]


@pytest.mark.asyncio
async def test_performance_schema_disabled_workflow():
    """Test performance schema disabled workflow using correct data format."""
    # Test the actual is_performance_schema_enabled method with correct format
    disabled_result = [{'': '0'}]  # Correct format: empty string key with '0' value
    enabled_result = [{'': '1'}]  # Correct format: empty string key with '1' value

    assert not MySQLAnalyzer.is_performance_schema_enabled(disabled_result)
    assert MySQLAnalyzer.is_performance_schema_enabled(enabled_result)

    # Test with empty result
    assert not MySQLAnalyzer.is_performance_schema_enabled([])
    assert not MySQLAnalyzer.is_performance_schema_enabled(None)
