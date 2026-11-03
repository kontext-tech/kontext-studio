"""
Schema management utilities for DuckDB sessions

This module contains the SchemaManager class for handling database schema
operations and introspection.
"""

import logging

from kontext.schema import SchemaInfo


class SchemaManager:
    """
    Manages schema information for DuckDB sessions
    """

    def __init__(self, connection, logger: logging.Logger):
        self.connection = connection
        self.logger = logger

    def create_schemas(self, schema_mapping: dict[str, str]) -> None:
        """
        Create schemas for all catalog namespaces

        Args:
            schema_mapping: Dictionary mapping schema names to namespace identifiers
        """
        for schema_name, namespace_id in schema_mapping.items():
            self.connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            self.logger.debug(f"Created schema '{schema_name}' for namespace {namespace_id}")

    def set_default_schema(self, schema_name: str | None) -> None:
        """
        Set the default schema for the session

        Args:
            schema_name: Schema name to set as default
        """
        if schema_name:
            self.connection.execute(f'SET search_path = "{schema_name}"')
            self.logger.info(f"Set default schema: {schema_name}")
        else:
            self.logger.info("No default schema set - using global namespace")

    def get_schema_info(self, schema_name: str | None = None) -> SchemaInfo:
        """
        Get information about the specified schema and available tables

        Args:
            schema_name: Schema name to query (None for main schema)

        Returns:
            SchemaInfo model containing schema information including name and table list
        """
        try:
            # Get current catalog
            catalog_result = self.connection.execute("SELECT current_catalog()").fetchone()
            current_catalog = catalog_result[0] if catalog_result else None

            # Get all tables in the current schema
            if schema_name:
                tables_result = self.connection.execute(
                    f"SELECT table_name FROM information_schema.tables "
                    f"WHERE table_schema = '{schema_name}'"
                ).fetchall()
            else:
                tables_result = self.connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()

            table_names = [row[0] for row in tables_result]

            # Generate qualified name
            qualified_name = (
                f"{current_catalog}.{schema_name}"
                if current_catalog and schema_name
                else schema_name
            )

            return SchemaInfo(
                catalog_name=current_catalog,
                schema_name=schema_name,
                owner=None,  # Not retrieved in this method
                qualified_name=qualified_name,
                table_names=table_names,
                table_count=len(table_names),
            )

        except Exception as e:
            self.logger.error(f"Failed to get schema info: {e}")
            raise

    def list_all_schemas(self) -> list[SchemaInfo]:
        """
        List all available schemas in the database with complete information

        Returns:
            List of SchemaInfo models containing schema information including tables
        """
        try:
            result = self.connection.execute(
                "SELECT catalog_name, schema_name, schema_owner "
                "FROM information_schema.schemata "
                "ORDER BY catalog_name, schema_name"
            ).fetchall()

            schemas = []
            for row in result:
                catalog_name = row[0]
                schema_name = row[1]
                owner = row[2]

                # Skip system schemas that we don't want to include
                if schema_name in ("information_schema", "pg_catalog"):
                    continue

                # Get detailed schema info including tables
                try:
                    schema_info = self.get_schema_info(schema_name)
                    # Update the owner information from the schema listing
                    schema_info.owner = owner
                    schemas.append(schema_info)
                except Exception as e:
                    self.logger.warning(f"Failed to get tables for schema {schema_name}: {e}")
                    # Fall back to basic schema info without tables
                    qualified_name = (
                        f"{catalog_name}.{schema_name}" if catalog_name != "system" else schema_name
                    )
                    schemas.append(
                        SchemaInfo(
                            catalog_name=catalog_name,
                            schema_name=schema_name,
                            owner=owner,
                            qualified_name=qualified_name,
                            table_names=None,
                            table_count=None,
                        )
                    )

            return schemas

        except Exception as e:
            self.logger.error(f"Failed to list schemas: {e}")
            raise
