"""Test configuration for DynamoDB MCP Server tests."""
import sys
import os

# Add the project root to Python path so tests can import local modules
project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
