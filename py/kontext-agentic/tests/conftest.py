"""
Shared test fixtures and configuration for kontext-agentic tests.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def load_test_env():
    """Load test environment variables."""
    env_file = Path(__file__).parent.parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)


@pytest.fixture
def mock_service_factory():
    """Create a mock service factory for testing."""
    factory = MagicMock()

    # Mock project service
    project_service = AsyncMock()
    factory.create_project_service.return_value = project_service

    # Mock catalog service
    catalog_service = AsyncMock()
    factory.create_catalog_service.return_value = catalog_service

    # Mock the get_service method
    factory.get_service.return_value = AsyncMock()

    return factory


@pytest.fixture
def mock_query_session_service():
    """Create a mock query session service for testing."""

    class MockResult:
        def __init__(self):
            self.success = True
            self.error_message = None
            mock_col = MagicMock()
            mock_col.name = "placeholder"
            mock_col.type = "string"
            self.columns = [mock_col]
            self.rows = [["data"]]
            self.row_count = 1
            self.execution_time_ms = 10
            self.data_id = None

    class MockResponse:
        def __init__(self):
            self.success = True
            self.error_message = None
            self.total_execution_time_ms = 10
            self.result = MockResult()
            self.data_id = None

    mock_response = MockResponse()
    query_session_service = MagicMock()
    query_session_service.execute_sql = AsyncMock(return_value=mock_response)
    query_session_service.execute_sql_with_session_management = AsyncMock(
        return_value=mock_response
    )
    query_session_service.get_or_create_session = AsyncMock(
        return_value="550e8400-e29b-41d4-a716-446655440000"
    )
    return query_session_service


@pytest.fixture
def mock_service_provider(mock_query_session_service):
    """Create a mock service provider for testing."""
    provider = MagicMock()
    provider.get_query_session_service.return_value = mock_query_session_service
    provider.get_catalog_service.return_value = MagicMock()
    provider.get_catalog_index_service.return_value = AsyncMock()
    file_service = MagicMock()
    file_service.exists_by_id = AsyncMock(return_value=False)
    file_service.get_file_content = AsyncMock()

    file_service.materialize_inline_data = AsyncMock(
        return_value="2eb96811-39fe-47a4-7e25-08de0be1d151"
    )
    file_service.get_data_table_file = AsyncMock()
    file_service.get_inline_data_rows = AsyncMock()
    provider.get_file_service.return_value = file_service
    provider.get_project_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None
    return provider


@pytest.fixture
def sample_project_data() -> dict[str, Any]:
    """Create sample project data for testing."""
    return {
        "id": "demo-project-id",
        "code": "demo-project",
        "name": "Demo Project",
        "description": "A demo project for testing",
        "is_active": True,
    }


@pytest.fixture
def sample_project():
    """Create a sample ProjectModel for testing."""
    from kontext.schema import ProjectModel

    # Use model_construct to bypass validation for testing
    return ProjectModel.model_construct(
        id="1eb96811-39fe-47a4-7e25-08de0be1d149",
        project_code="test-project",
        project_name="Test Project",
        project_description="A test project",
        access_level="Private",
        configuration={},
        owner_id="1eb96811-39fe-47a4-7e25-08de0be1d150",
    )


@pytest.fixture
def sample_sql_queries() -> dict[str, dict[str, Any]]:
    """Sample SQL queries and their expected components for testing."""
    return {
        "simple_count": {
            "question": "How many customers are there?",
            "expected_sql_patterns": ["SELECT", "COUNT", "customers"],
            "expected_tables": ["customers"],
        },
        "join_query": {
            "question": "What are the top 5 customers by total transaction amount?",
            "expected_sql_patterns": [
                "SELECT",
                "SUM",
                "JOIN",
                "GROUP BY",
                "ORDER BY",
                "LIMIT",
            ],
            "expected_tables": ["customers", "transactions"],
        },
        "filter_query": {
            "question": "Show me all pending transactions",
            "expected_sql_patterns": ["SELECT", "WHERE", "status", "pending"],
            "expected_tables": ["transactions"],
        },
    }


@pytest.fixture
def mock_query_execution_result():
    """Mock result from query execution."""
    return {
        "success": True,
        "data": [
            {"customer_count": 150},
        ],
        "columns": ["customer_count"],
        "execution_time_ms": 45,
        "row_count": 1,
    }
