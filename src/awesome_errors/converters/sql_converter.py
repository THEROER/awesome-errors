import re
from typing import Dict, Optional, Tuple
from sqlalchemy.exc import (
    IntegrityError,
    DataError,
    OperationalError,
    ProgrammingError,
    DatabaseError as SQLAlchemyDatabaseError,
)

from ..core.error_codes import ErrorCode
from ..core.exceptions import DatabaseError


class SQLErrorConverter:
    """Convert SQLAlchemy errors to application errors."""

    # Regex patterns for common SQL errors
    SQL_PATTERNS: Dict[re.Pattern, Tuple[ErrorCode, str]] = {
        # PostgreSQL patterns
        re.compile(r"duplicate key value violates unique constraint"): (
            ErrorCode.DB_DUPLICATE_ENTRY,
            "Record already exists",
        ),
        re.compile(r"violates foreign key constraint"): (
            ErrorCode.DB_INVALID_REFERENCE,
            "Invalid reference to related record",
        ),
        re.compile(r"violates not-null constraint"): (
            ErrorCode.DB_MISSING_REQUIRED,
            "Required field is missing",
        ),
        re.compile(r"violates check constraint"): (
            ErrorCode.DB_CONSTRAINT_VIOLATION,
            "Value violates constraint",
        ),
        # MySQL patterns
        re.compile(r"Duplicate entry .* for key"): (
            ErrorCode.DB_DUPLICATE_ENTRY,
            "Record already exists",
        ),
        re.compile(
            r"Cannot add or update a child row: a foreign key constraint fails"
        ): (ErrorCode.DB_INVALID_REFERENCE, "Invalid reference to related record"),
        re.compile(r"Column .* cannot be null"): (
            ErrorCode.DB_MISSING_REQUIRED,
            "Required field is missing",
        ),
        # SQLite patterns
        re.compile(r"UNIQUE constraint failed"): (
            ErrorCode.DB_DUPLICATE_ENTRY,
            "Record already exists",
        ),
        re.compile(r"FOREIGN KEY constraint failed"): (
            ErrorCode.DB_INVALID_REFERENCE,
            "Invalid reference to related record",
        ),
        re.compile(r"NOT NULL constraint failed"): (
            ErrorCode.DB_MISSING_REQUIRED,
            "Required field is missing",
        ),
    }

    @classmethod
    def convert(cls, error: Exception) -> DatabaseError:
        """Convert SQLAlchemy error to DatabaseError."""
        if isinstance(error, IntegrityError):
            return cls._convert_integrity_error(error)
        elif isinstance(error, DataError):
            return cls._convert_data_error(error)
        elif isinstance(error, OperationalError):
            return cls._convert_operational_error(error)
        elif isinstance(error, ProgrammingError):
            return cls._convert_programming_error(error)
        elif isinstance(error, SQLAlchemyDatabaseError):
            return cls._convert_generic_database_error(error)
        else:
            return DatabaseError(
                message=str(error), code=ErrorCode.DB_QUERY_ERROR, sql_error=str(error)
            )

    @classmethod
    def _convert_integrity_error(cls, error: IntegrityError) -> DatabaseError:
        """Convert IntegrityError to DatabaseError with detailed field information."""
        error_str = str(error.orig) if error.orig else str(error)

        # Check patterns
        for pattern, (code, message) in cls.SQL_PATTERNS.items():
            if pattern.search(error_str):
                db_error = DatabaseError(
                    message=message,
                    code=code,
                    sql_error=error_str,
                    table=cls._extract_table_name(error_str),
                )

                # Add detailed field information
                field_name = cls._extract_field_name(error_str)
                if field_name:
                    db_error.details["field"] = field_name

                constraint_name = cls._extract_constraint_name(error_str)
                if constraint_name:
                    db_error.details["constraint"] = constraint_name

                # For duplicate entries, extract the duplicate value
                if code == ErrorCode.DB_DUPLICATE_ENTRY:
                    duplicate_value = cls._extract_duplicate_value(error_str)
                    if duplicate_value:
                        db_error.details["duplicate_value"] = duplicate_value
                        db_error.message = (
                            f"{message}: {field_name}={duplicate_value}"
                            if field_name
                            else f"{message}: {duplicate_value}"
                        )

                # For missing required fields
                elif code == ErrorCode.DB_MISSING_REQUIRED and field_name:
                    db_error.message = f"{message}: {field_name}"

                # For invalid references
                elif code == ErrorCode.DB_INVALID_REFERENCE and field_name:
                    db_error.message = f"{message} in field: {field_name}"

                if db_error.details.get("table"):
                    db_error.details["table"] = db_error.details["table"]

                return db_error

        # Default integrity error
        return DatabaseError(
            message="Database integrity constraint violated",
            code=ErrorCode.DB_CONSTRAINT_VIOLATION,
            sql_error=error_str,
        )

    @classmethod
    def _convert_data_error(cls, error: DataError) -> DatabaseError:
        """Convert DataError to DatabaseError."""
        return DatabaseError(
            message="Invalid data format",
            code=ErrorCode.INVALID_FORMAT,
            sql_error=str(error.orig) if error.orig else str(error),
        )

    @classmethod
    def _convert_operational_error(cls, error: OperationalError) -> DatabaseError:
        """Convert OperationalError to DatabaseError."""
        error_str = str(error.orig) if error.orig else str(error)

        if "connection" in error_str.lower():
            return DatabaseError(
                message="Database connection error",
                code=ErrorCode.DB_CONNECTION_ERROR,
                sql_error=error_str,
            )

        return DatabaseError(
            message="Database operational error",
            code=ErrorCode.DB_QUERY_ERROR,
            sql_error=error_str,
        )

    @classmethod
    def _convert_programming_error(cls, error: ProgrammingError) -> DatabaseError:
        """Convert ProgrammingError to DatabaseError."""
        return DatabaseError(
            message="Database programming error",
            code=ErrorCode.DB_QUERY_ERROR,
            sql_error=str(error.orig) if error.orig else str(error),
        )

    @classmethod
    def _convert_generic_database_error(
        cls, error: SQLAlchemyDatabaseError
    ) -> DatabaseError:
        """Convert generic DatabaseError to DatabaseError."""
        return DatabaseError(
            message="Database error occurred",
            code=ErrorCode.DB_QUERY_ERROR,
            sql_error=str(error.orig) if error.orig else str(error),
        )

    @classmethod
    def _extract_table_name(cls, error_str: str) -> Optional[str]:
        """Extract table name from error string."""
        # PostgreSQL pattern
        match = re.search(r'relation "([^"]+)"', error_str)
        if match:
            return match.group(1)

        # MySQL pattern
        match = re.search(r"`([^`]+)`\.`([^`]+)`", error_str)
        if match:
            return match.group(2)

        # SQLite pattern
        match = re.search(r"table (\w+)", error_str)
        if match:
            return match.group(1)

        return None

    @classmethod
    def _extract_field_name(cls, error_str: str) -> Optional[str]:
        """Extract field/column name from error string."""
        # PostgreSQL patterns
        match = re.search(r'column "([^"]+)"', error_str)
        if match:
            return match.group(1)

        # MySQL patterns
        match = re.search(r"Column '([^']+)'", error_str)
        if match:
            return match.group(1)

        # SQLite patterns
        match = re.search(r"column (\w+)", error_str)
        if match:
            return match.group(1)

        return None

    @classmethod
    def _extract_constraint_name(cls, error_str: str) -> Optional[str]:
        """Extract constraint name from error string."""
        # PostgreSQL pattern
        match = re.search(r'constraint "([^"]+)"', error_str)
        if match:
            return match.group(1)

        # MySQL pattern
        match = re.search(r"key '([^']+)'", error_str)
        if match:
            return match.group(1)

        return None

    @classmethod
    def _extract_duplicate_value(cls, error_str: str) -> Optional[str]:
        """Extract duplicate value from error string."""
        # PostgreSQL pattern
        match = re.search(r"Key \([^)]+\)=\(([^)]+)\)", error_str)
        if match:
            return match.group(1)

        # MySQL pattern
        match = re.search(r"Duplicate entry '([^']+)'", error_str)
        if match:
            return match.group(1)

        return None
