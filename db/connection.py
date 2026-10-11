# PURPOSE
# Create a reusable connection to the MySQL database.
#
# INPUT
# Configuration loaded from environment variables:
# DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
#
# OUTPUT
# A database connection that other scripts can use.
#
# EXPECTED BEHAVIOR
# Read configuration.
# Check that required settings exist.
# Connect using mysql-connector-python.
# Use UTC consistently for database timestamps.
# Return the connection.
# Close connections when work is complete.
#
# IMPORTANT
# Do not put real passwords in this file or commit them to GitHub.
# Keep local credentials in an ignored .env file.
# Commit an .env.example containing placeholders.
# Application scripts should use an application account.
#
# LOCAL DEVELOPMENT
# Each mentee can run their own MySQL instance.
# Everyone shares the same schema and configuration variable names.
# Separate local databases do not automatically share their records.
#
# TODO
# Implement a connect() function.
# Write a small connection check using SELECT DATABASE(), VERSION().
# Explain the difference between MySQL and MySQL Workbench.
#
# QUESTIONS
# What is a database host?
# What is a port?
# What could cause "connection refused"?
# What could cause "access denied"?