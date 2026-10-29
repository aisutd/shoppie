import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "shoppie.db"

def main() -> None:
    #Connecting creates the database file if it doesn't exist 
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row # This allows us to access columns by name rather than just "row[2] or something"

    try: 
        with connection:
            connection.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY,
                retailer TEXT NOT NULL,
                title TEXT NOT NULL,
                model TEXT,
                price_cents INTEGER
            )
            """)

        example = (
            "Best Buy",
            "Apple IPhone 15 Pro Max",
            "IPhone 15 Pro Max",
            99999,
        )
        #lesson convenience, not future listing identity rule 


        #checks for duplicates
        existing = connection.execute("""
            SELECT * FROM listings WHERE retailer = ? AND title = ? AND model = ? AND price_cents = ?
            LIMIT 1
        """, example).fetchone()


        #creates new listing to store into database if it doesn't already exist
        if existing is None:
            #placeholder for future listing identity rule from SQL instructions
            connection.execute("""
            INSERT INTO listings (retailer, title, model, price_cents)
            VALUES (?, ?, ?, ?)
            """, example)
            print("Saved the example listing.")

        else:
            print("The example listing already exists in the database.")

        #At this point, transaction saved any changes
        # Retrieve everything from the table
        rows = connection.execute("""
            SELECT id, retailer, title, model, price_cents
            FROM listings ORDER BY id
        """).fetchall()

        print(f"Database: {DATABASE_PATH}")
        print(f"Stored listings: {len(rows)}")
        for row in rows:
            cents = row["price_cents"]
            #Money stored in cents, but we want to display in dollars

            price = "Unknown" if cents is None else f"${cents / 100:.2f}"
            print(f"ID: {row['id']}, Retailer: {row['retailer']}, Title: {row['title']}, Model: {row['model']}, Price: {price}")   

    finally:
        #release connection to db even if statement fails so we're not stuck at failure

        connection.close()

if __name__ == "__main__":
    main() 