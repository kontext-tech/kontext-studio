import unittest
import uuid
from unittest.mock import MagicMock, patch

from kontext.jobs.schema_profiler.excel_profiler import ExcelSchemaProfiler
from kontext.jobs.schema_profiler.models import ProfilerParameters
from kontext.schema import FileFormatType


class TestExcelSchemaProfiler(unittest.TestCase):
    def setUp(self):
        self.params = ProfilerParameters(
            uri="az://container/test.xlsx",
            file_type=FileFormatType.EXCEL,
            file_name="test.xlsx",
            project_id=uuid.uuid4(),
        )

    @patch("kontext.jobs.schema_profiler.profiler_base.duckdb")
    def test_profile_success(self, mock_duckdb):
        # Setup mocks
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        # Mock DESCRIBE output
        # (column_name, column_type, null, key, default, extra)
        mock_conn.execute.return_value.fetchall.side_effect = [
            [
                ("col1", "INTEGER", "YES", None, None, None),
                ("col2", "VARCHAR", "NO", None, None, None),
            ],  # DESCRIBE
        ]

        # Mock COUNT(*) output
        mock_conn.execute.return_value.fetchone.side_effect = [
            (100),  # row count
            (0),  # null count col1
            (50),  # distinct count col1
            (100),  # total count col1
            (0, 10, 5, 2),  # numeric stats col1
            (0),  # null count col2
            (100),  # distinct count col2
            (100),  # total count col2
            (20),  # text stats col2
        ]

        with ExcelSchemaProfiler(self.params) as profiler:
            # Manually set connection since we're mocking the init
            profiler._connection = mock_conn

            # Mock the sheet discovery to return a single sheet
            with patch.object(profiler, "_discover_sheet_names", return_value=["Sheet1"]):
                result = profiler.profile()

            self.assertTrue(result.success)
            self.assertIsNotNone(result.file_schema)
            self.assertIsNotNone(result.file_stats)

            # Type narrowing for Pylance
            assert result.file_schema is not None
            assert result.file_stats is not None
            assert result.file_schema.sub_schemas is not None
            assert len(result.file_schema.sub_schemas) > 0
            assert result.file_stats.sub_schemas is not None
            assert len(result.file_stats.sub_schemas) > 0

            # Get first sub-schema (single-table file has one item)
            sub_schema = result.file_schema.sub_schemas[0]
            sub_stats = result.file_stats.sub_schemas[0]

            # Verify schema
            self.assertEqual(len(sub_schema.columns), 2)
            self.assertEqual(sub_schema.columns[0].name, "col1")
            self.assertEqual(sub_schema.columns[0].nullable, True)
            self.assertEqual(sub_schema.columns[1].name, "col2")
            self.assertEqual(sub_schema.columns[1].nullable, False)

            # Verify stats
            assert sub_stats.column_stats is not None
            self.assertEqual(len(sub_stats.column_stats), 2)
            self.assertEqual(sub_stats.estimated_row_count, 100)
            self.assertEqual(sub_stats.column_stats[0].distinct_count, 50)
            self.assertEqual(sub_stats.column_stats[1].distinct_count, 100)

    @patch("kontext.jobs.schema_profiler.profiler_base.duckdb")
    def test_sql_escaping(self, mock_duckdb):
        # Test SQL escaping with sheet name passed directly
        self.params.uri = "az://container/file'name.xlsx"

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        with ExcelSchemaProfiler(self.params) as profiler:
            profiler._connection = mock_conn
            # Pass sheet name directly to _create_excel_view
            profiler._create_excel_view("Sheet'1")

            # Verify SQL contains escaped single quotes and correct parameters
            calls = mock_conn.execute.call_args_list
            found_sql = False
            for call in calls:
                sql = call[0][0]
                if "read_xlsx" in sql:
                    self.assertIn("'az://container/file''name.xlsx'", sql)
                    self.assertIn("sheet='Sheet''1'", sql)
                    found_sql = True
            self.assertTrue(found_sql)

    @patch("kontext.jobs.schema_profiler.excel_profiler.load_workbook")
    def test_discover_sheet_names_resolves_file_uri_for_openpyxl(self, mock_load_workbook):
        self.params.uri = "file:///tmp/sales_orders.xlsx"
        fake_workbook = MagicMock()
        fake_workbook.sheetnames = ["Products", "Order Items"]
        mock_load_workbook.return_value = fake_workbook

        profiler = ExcelSchemaProfiler(self.params)

        with patch("kontext.jobs.schema_profiler.excel_profiler.HAS_OPENPYXL", True):
            sheet_names = profiler._discover_sheet_names()

        self.assertEqual(sheet_names, ["Products", "Order Items"])
        mock_load_workbook.assert_called_once_with(
            "/tmp/sales_orders.xlsx", read_only=True, data_only=True
        )
        fake_workbook.close.assert_called_once()

    @patch("kontext.jobs.schema_profiler.profiler_base.duckdb")
    def test_profile_falls_back_to_default_sheet_without_inventing_sheet1(self, mock_duckdb):
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchall.side_effect = [
            [("order_id", "INTEGER", "YES", None, None, None)],
        ]
        mock_conn.execute.return_value.fetchone.side_effect = [
            12,
            0,
            12,
            12,
            (1, 12, 6.5, 2.0),
        ]

        with ExcelSchemaProfiler(self.params) as profiler:
            profiler._connection = mock_conn

            with patch.object(profiler, "_discover_sheet_names", return_value=[]):
                result = profiler.profile()

        self.assertTrue(result.success)
        assert result.file_schema is not None
        assert result.file_stats is not None
        assert result.file_schema.sub_schemas is not None
        assert result.file_schema.metadata.format_specific_metadata is not None
        self.assertEqual(result.file_schema.sub_schemas[0].table_name, "test.xlsx")
        self.assertEqual(
            result.file_schema.metadata.format_specific_metadata["sheet_names"],
            ["default"],
        )

        read_xlsx_calls = [
            call[0][0] for call in mock_conn.execute.call_args_list if "read_xlsx" in call[0][0]
        ]
        self.assertEqual(len(read_xlsx_calls), 1)
        self.assertNotIn("sheet=", read_xlsx_calls[0])
        self.assertNotIn("Sheet1", read_xlsx_calls[0])


if __name__ == "__main__":
    unittest.main()
