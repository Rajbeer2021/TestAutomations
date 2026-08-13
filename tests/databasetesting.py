'''
import unittest
from utils.dbUtils import DatabaseUtils

class TestDatabaseUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # MySQL / SQL Server connection info
        cls.mysql_config = {
            "db_type": "mysql",
            "host": "localhost",
            "database": "test_db",
            "user": "root",
            "password": "password",
            "port": 3306
        }
        cls.sqlserver_config = {
            "db_type": "sqlserver",
            "host": "localhost",
            "database": "test_db",
            "user": "sa",
            "password": "Password123"
        }
        cls.mongodb_config = {
            "db_type": "mongodb",
            "host": "localhost",
            "port": 27017,
            "database": "test_db"
        }

    # ---------------- MySQL Tests ----------------
    def test_mysql_crud(self):
        db = DatabaseUtils(**self.mysql_config)

        # Create table
        db.execute_non_query("CREATE TABLE IF NOT EXISTS test_table (id INT PRIMARY KEY, name VARCHAR(50))")

        # Insert
        db.execute_non_query("INSERT INTO test_table (id, name) VALUES (%s, %s)", (1, "Alice"))

        # Select
        result = db.execute_query("SELECT * FROM test_table WHERE id=%s", (1,))
        self.assertEqual(result[0]["name"], "Alice")

        # Update
        db.execute_non_query("UPDATE test_table SET name=%s WHERE id=%s", ("Bob", 1))
        result = db.execute_query("SELECT * FROM test_table WHERE id=%s", (1,))
        self.assertEqual(result[0]["name"], "Bob")

        # Delete
        db.execute_non_query("DELETE FROM test_table WHERE id=%s", (1,))
        result = db.execute_query("SELECT * FROM test_table WHERE id=%s", (1,))
        self.assertEqual(len(result), 0)

        # Drop table
        db.execute_non_query("DROP TABLE test_table")
        db.close()

    # ---------------- SQL Server Tests ----------------
    def test_sqlserver_crud(self):
        db = DatabaseUtils(**self.sqlserver_config)

        # Create table
        db.execute_non_query(
            "IF OBJECT_ID('dbo.test_table', 'U') IS NULL CREATE TABLE test_table (id INT PRIMARY KEY, name NVARCHAR(50))")

        # Insert
        db.execute_non_query("INSERT INTO test_table (id, name) VALUES (?, ?)", (1, "Alice"))

        # Select
        result = db.execute_query("SELECT * FROM test_table WHERE id=?", (1,))
        self.assertEqual(result[0]["name"], "Alice")

        # Update
        db.execute_non_query("UPDATE test_table SET name=? WHERE id=?", ("Bob", 1))
        result = db.execute_query("SELECT * FROM test_table WHERE id=?", (1,))
        self.assertEqual(result[0]["name"], "Bob")

        # Delete
        db.execute_non_query("DELETE FROM test_table WHERE id=?", (1,))
        result = db.execute_query("SELECT * FROM test_table WHERE id=?", (1,))
        self.assertEqual(len(result), 0)

        # Drop table
        db.execute_non_query("DROP TABLE test_table")
        db.close()

    # ---------------- MongoDB Tests ----------------
    def test_mongodb_crud(self):
        db = DatabaseUtils(**self.mongodb_config)
        collection = "test_collection"

        # Insert
        doc_id = db.insert_document(collection, {"_id": 1, "name": "Alice"})
        self.assertIsNotNone(doc_id)

        # Find
        docs = db.find_documents(collection, {"_id": 1})
        self.assertEqual(docs[0]["name"], "Alice")

        # Update
        modified_count = db.update_documents(collection, {"_id": 1}, {"name": "Bob"})
        self.assertEqual(modified_count, 1)
        docs = db.find_documents(collection, {"_id": 1})
        self.assertEqual(docs[0]["name"], "Bob")

        # Delete
        deleted_count = db.delete_documents(collection, {"_id": 1})
        self.assertEqual(deleted_count, 1)
        docs = db.find_documents(collection, {"_id": 1})
        self.assertEqual(len(docs), 0)

        db.close()


if __name__ == "__main__":
    unittest.main()
'''