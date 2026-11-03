"""
Validation constants shared by file and lakehouse-adjacent APIs.

Contains regex patterns and retained compatibility messages.
"""

# SQL identifier pattern
# Starts with letter/underscore, alphanumeric + underscores only
SQL_IDENTIFIER_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"

# Part name pattern - more permissive, allows hyphens
PART_NAME_PATTERN = r"^[a-zA-Z0-9_-]+$"
