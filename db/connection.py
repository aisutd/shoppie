"""Step 3: share one MySQL connection method across the database scripts.

MySQL is the running database server; Workbench is a client used to view it.
Install mysql-connector-python when implementing this file. Import it inside
connect() so students can read/import this skeleton before installing it.
"""


def read_config() -> dict:
    """Read connection settings so credentials do not live in source code."""
    # TODO: Read DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD from environment.
    # TODO: Validate required settings; convert DB_PORT to an integer.
    # A .env file is not loaded automatically: document shell exports OR use
    # python-dotenv explicitly. Never print the password in diagnostics.
    raise NotImplementedError("Mentee TODO: read database configuration")


def connect():
    """Return an open MySQL connection; the caller closes it after use."""
    # TODO: Call read_config(), then mysql.connector.connect(**config).
    # TODO: Set the session time zone to '+00:00' and autocommit=False.
    # Database must already exist (mentor provisions it in Step 2).
    # TODO: Give connection failures a helpful message without credentials.
    raise NotImplementedError("Mentee TODO: connect to MySQL")


def describe_connection(connection) -> dict:
    """Show which database/server a student actually connected to."""
    # TODO: SELECT DATABASE(), VERSION(); return database and version.
    # TODO: Close the cursor; leave the caller's connection open.
    raise NotImplementedError("Mentee TODO: describe connection")
