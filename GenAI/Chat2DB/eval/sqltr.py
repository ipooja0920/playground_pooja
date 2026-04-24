"""
SQL Test Runner - Executes SQL queries against the domain database
and returns results as DataFrames for comparison.
"""

import sys
import os
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chat2db'))
from tools.db import DatabaseManager


class SQLTestRunner:
    """Executes SQL queries against the Chinook database for evaluation."""

    def __init__(self):
        """Initialize with database connection in dev mode."""
        os.environ['ENV'] = 'dev'
        self.db_manager = DatabaseManager(db_type='db')
        if not self.db_manager.test_connection():
            raise ConnectionError("Could not connect to the database")

    def execute(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a DataFrame.
        
        Args:
            query: SQL query string
            
        Returns:
            DataFrame with query results, or empty DataFrame on error
        """
        try:
            results = self.db_manager.execute_query(query)
            if results is None:
                return pd.DataFrame()
            return pd.DataFrame(results)
        except Exception as e:
            print(f"Error executing query: {e}")
            return pd.DataFrame()

    def compare_results(self, generated_sql: str, expected_sql: str) -> dict:
        """Compare results of generated SQL vs expected SQL.
        
        Returns:
            Dict with results, match status, and any errors
        """
        gen_result = self.execute(generated_sql)
        exp_result = self.execute(expected_sql)

        # Check if results are identical
        try:
            match = gen_result.equals(exp_result)
        except Exception:
            match = False

        return {
            "generated_results": gen_result,
            "expected_results": exp_result,
            "match": match,
            "generated_rows": len(gen_result),
            "expected_rows": len(exp_result),
        }


if __name__ == "__main__":
    # Quick test
    runner = SQLTestRunner()
    df = runner.execute("SELECT COUNT(*) FROM track")
    print(f"Track count: {df}")
