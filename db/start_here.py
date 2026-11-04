import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "shoppie.db"


def main() -> None:
    # Connection creates the database file if it does not already exist
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    # this will show the title of the row rather than show "row[2]" it just makes it a lil easier for us to view

    try:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY,
                    retailer TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT,
                    price_cents INTEGER
                )
                """
            )

            example = (
                "Best-Buy",
                "Apple AirPods Pro Max",
                "Airpods Pro Max",
                59999,
            )

            # This is a team convience not our future listing identity rule
            # checks for duplicates or if object already exists
            existing = connection.execute(
                """
                SELECT id FROM listings
                WHERE retailer = ? AND title = ? AND model = ? AND price_cents = ?
                LIMIT 1
                """,
                example,
            ).fetchone()

            # creates now listing to store into the database
            if existing is None:
                # Placeholders keep values seperate from the SQL command, preventing SQL instructions
                connection.execute(
                    """
                    INSERT INTO listings (retailer, title, model, price_cents)
                    VALUES (?, ?, ?, ?)
                    """,
                    example,
                )
                print("Saved the example listing.")
            else:
                print("The example is already saved.")

        # At this point the transaction has saved any changes
        rows = connection.execute(
            """
            SELECT id, retailer, title, model, price_cents
            FROM listings ORDER BY id
            """
        ).fetchall()

        print(f"Database: {DATABASE_PATH}")
        print(f"Stored listings: {len(rows)}")
        for row in rows:
            cents = row["price_cents"]
            # Money is stored as integer cents, formatting is only for display
            price = "Unknown" if cents is None else f"${cents // 100}.{cents % 100:02d}"
            model = row["model"] if row["model"] is not None else "Unknown"
            print(f"  [{row['id']}] {row['retailer']} | {row['title']} | {model} | {price}")
    finally:
        # release the connection to the db even if a statement fails so we're not stuck there
        connection.close()


if __name__ == "__main__":
    main()