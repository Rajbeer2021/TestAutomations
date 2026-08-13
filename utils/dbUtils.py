import mysql.connector
import pyodbc
from pymongo import MongoClient
from utils.logger import get_logger
import json


class DatabaseUtils:

    def __init__(self, db_type, host, database=None, user=None, password=None, port=None, mongo_uri=None,
                 reporter=None):
        self.db_type = db_type.lower()
        self.conn = None
        self.cursor = None
        self.logger = get_logger(name="DatabaseUtils", log_file="reports/logs/db.log")
        self.reporter = reporter  # Optional reference for logging/reporting

        if self.db_type == "mysql":
            self.conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                port=port or 3306
            )
            self.cursor = self.conn.cursor(dictionary=True)

        elif self.db_type == "sqlserver":
            self.conn = pyodbc.connect(
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={host};"
                f"DATABASE={database};"
                f"UID={user};"
                f"PWD={password}"
            )
            self.cursor = self.conn.cursor()

        elif self.db_type == "mongodb":
            self.client = MongoClient(mongo_uri or f"mongodb://{host}:{port or 27017}/")
            self.db = self.client[database]

        else:
            raise ValueError("Unsupported database type. Choose 'mysql', 'sqlserver', or 'mongodb'.")

    # ---------------- MySQL / SQLServer Methods ----------------

    def execute_query(self, query, params=None):
        if self.db_type in ["mysql", "sqlserver"]:
            self.cursor.execute(query, params or ())
            columns = [col[0] for col in self.cursor.description]
            rows = self.cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        else:
            raise ValueError("execute_query() not supported for MongoDB")

    def execute_non_query(self, query, params=None):
        if self.db_type in ["mysql", "sqlserver"]:
            self.cursor.execute(query, params or ())
            self.conn.commit()
        else:
            raise ValueError("execute_non_query() not supported for MongoDB")

    # ---------------- MongoDB Methods ----------------

    def insert_document(self, collection_name, document):
        if self.db_type != "mongodb":
            raise ValueError("insert_document() only supported for MongoDB")
        collection = self.db[collection_name]
        return collection.insert_one(document).inserted_id

    def find_documents(self, collection_name, query=None):
        if self.db_type != "mongodb":
            raise ValueError("find_documents() only supported for MongoDB")
        collection = self.db[collection_name]
        return list(collection.find(query or {}))

    def update_documents(self, collection_name, filter_query, update_values):
        if self.db_type != "mongodb":
            raise ValueError("update_documents() only supported for MongoDB")
        collection = self.db[collection_name]
        return collection.update_many(filter_query, {"$set": update_values}).modified_count

    def delete_documents(self, collection_name, filter_query):
        if self.db_type != "mongodb":
            raise ValueError("delete_documents() only supported for MongoDB")
        collection = self.db[collection_name]
        return collection.delete_many(filter_query).deleted_count

    # ---------------- Common ----------------

    def close(self):
        """Close database connection."""
        if self.db_type in ["mysql", "sqlserver"]:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        elif self.db_type == "mongodb":
            self.client.close()

    # ---------------- Assertion-like methods ----------------

    def _assert(self, condition: bool, message: str):
        """Central assertion method for all checks."""
        if not condition:
            self.logger.error(f"Assertion Failed: {message}")
            raise AssertionError(message)
        else:
            self.logger.info(f"Assertion Passed: {message}")

    def _log_step(self, step_name: str, func, screenshot=False):
        """Optional wrapper for logging/reporting steps."""
        try:
            func()
            self.logger.info(f"[PASS] {step_name}")
        except AssertionError as e:
            self.logger.error(f"[FAIL] {step_name} — {e}")
            raise

    # ---------------- Basic DB Assertions ----------------

    def assertDBValue(self, collection_or_query, key=None, expected_value=None, step_name="Assert DB Value", screenshot=False):
        """Check if a specific value matches in SQL or MongoDB."""
        def func():
            if self.db_type in ["mysql", "sqlserver"]:
                result = self.execute_query(collection_or_query)
                self._assert(result, "No rows returned")
                actual = result[0][key] if key else result[0]
            elif self.db_type == "mongodb":
                docs = self.find_documents(collection_or_query)
                self._assert(docs, "No documents found")
                actual = docs[0][key] if key else docs[0]
            else:
                self._assert(False, "Unsupported DB type for assertions")
            self._assert(actual == expected_value, f"Expected '{expected_value}', got '{actual}'")
        self._log_step(step_name, func, screenshot)

    def assertDBRowExists(self, collection_or_query, filter_or_params=None, step_name="Assert DB Row Exists", screenshot=False):
        """Check if row/document exists."""
        def func():
            if self.db_type in ["mysql", "sqlserver"]:
                result = self.execute_query(collection_or_query, filter_or_params)
            elif self.db_type == "mongodb":
                result = self.find_documents(collection_or_query, filter_or_params)
            self._assert(result, "Expected row/document to exist")
        self._log_step(step_name, func, screenshot)

    def assertDBRowNotExists(self, collection_or_query, filter_or_params=None, step_name="Assert DB Row Not Exists", screenshot=False):
        """Check if row/document does NOT exist."""
        def func():
            if self.db_type in ["mysql", "sqlserver"]:
                result = self.execute_query(collection_or_query, filter_or_params)
            elif self.db_type == "mongodb":
                result = self.find_documents(collection_or_query, filter_or_params)
            self._assert(not result, "Expected row/document to NOT exist")
        self._log_step(step_name, func, screenshot)

    # ---------------- General Assertions ----------------

    def assertEqual(self, actual, expected, step_name="Assert Equal", screenshot=False):
        self._log_step(step_name, lambda: self._assert(actual == expected, f"Expected '{expected}', got '{actual}'"), screenshot)

    def assertContains(self, container, item, step_name="Assert Contains", screenshot=False):
        self._log_step(step_name, lambda: self._assert(item in container, f"Expected '{container}' to contain '{item}'"), screenshot)

    def assertJSONMatch(self, actual_json, expected_json, step_name="Assert JSON Match", screenshot=False):
        """
        Compare two dicts/JSON objects
        """
        def func():
            actual_str = json.dumps(actual_json, sort_keys=True)
            expected_str = json.dumps(expected_json, sort_keys=True)
            self._assert(actual_str == expected_str, f"JSON does not match. Expected: {expected_json}, Got: {actual_json}")
        self._log_step(step_name, func, screenshot)

    def assertFind(self, collection_or_query, key=None, value=None, step_name="Assert Find Value", screenshot=False):
        """Check if a value exists in SQL results or MongoDB documents."""
        def func():
            if self.db_type in ["mysql", "sqlserver"]:
                rows = self.execute_query(collection_or_query)
                found = any(row.get(key) == value for row in rows) if key else any(row == value for row in rows)
            elif self.db_type == "mongodb":
                docs = self.find_documents(collection_or_query)
                found = any(doc.get(key) == value for doc in docs) if key else any(doc == value for doc in docs)
            else:
                found = False
            self._assert(found, f"Value '{value}' not found")
        self._log_step(step_name, func, screenshot)

    # ----------------- Smart Fetch / Select -----------------
    def fetch_records(self, table_or_collection, filters=None, columns=None, limit=None, sort=None):
        """
        Fetch records from MySQL / SQL Server / MongoDB in a unified way.

        :param table_or_collection: Table name (SQL) or collection name (MongoDB)
        :param filters: dict of conditions. For SQL, keys are columns and values are exact match.
        :param columns: list of columns to return (SQL only). For MongoDB, list of fields.
        :param limit: int, maximum number of records to fetch
        :param sort: dict, e.g., {"salary": -1} for MongoDB or {"salary": "DESC"} for SQL
        :return: list of dicts
        """
        if self.db_type in ["mysql", "sqlserver"]:
            # Build SQL query
            sql = "SELECT "

            # Columns or *
            if columns:
                sql += ", ".join(columns)
            else:
                sql += "*"

            sql += f" FROM {table_or_collection}"

            params = []
            # Filters
            if filters:
                conditions = []
                for k, v in filters.items():
                    conditions.append(f"{k} = %s")
                    params.append(v)
                sql += " WHERE " + " AND ".join(conditions)

            # Sort
            if sort:
                order_clause = ", ".join([f"{k} {v}" for k, v in sort.items()])
                sql += f" ORDER BY {order_clause}"

            # Limit
            if limit:
                if self.db_type == "mysql":
                    sql += f" LIMIT {limit}"
                elif self.db_type == "sqlserver":
                    # SQL Server uses TOP, modify query
                    top_clause = f"TOP {limit} "
                    sql = sql.replace("SELECT ", f"SELECT {top_clause}", 1)

            return self.execute_query(sql, params)

        elif self.db_type == "mongodb":
            # MongoDB query
            query = filters or {}
            projection = {k: 1 for k in columns} if columns else None
            cursor = self.db[table_or_collection].find(query, projection)

            # Sort
            if sort:
                # MongoDB sort expects list of tuples [(field, direction)]
                mongo_sort = [(k, v if v in [1, -1] else (-1 if str(v).upper() == "DESC" else 1)) for k, v in
                              sort.items()]
                cursor = cursor.sort(mongo_sort)

            # Limit
            if limit:
                cursor = cursor.limit(limit)

            return list(cursor)

        else:
            raise ValueError("Unsupported DB type for fetch_records")
