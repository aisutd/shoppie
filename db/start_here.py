import sqlite3
from pathlib import Path

#creating a database file
DATABASE_PATH = Path(__file__).resolve().parent / "shoppie.db"

def main() -> None:
    # Open a database file, creating it if it does not exist.
    connection = sqlite3.connect(DATABASE_PATH)
    #show the title of the row rather than the index of the row
    connection.row_factory = sqlite3.Row 

    try:
        with connection:
            # Create a table to hold retailer listings.
            connection.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY,
                    retailer TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT,
                    price_cents INTEGER
                )
            """)
        # Insert one retailer listing. Store money as integer cents.
        example = (
            "Amazon",
            "Airpods Pro (2nd Generation)",
            "MQD83AM/A",
            24900
        )

        existing = connection.execute("""
            SELECT id FROM listings
            WHERE retailer = ? AND title = ? AND model = ? AND price_cents = ?
            LIMIT 1
        """, example).fetchone()

        if existing is None:
            #placeholders keep values seperate from SQL instructions
            connection.execute("""
                INSERT INTO listings (retailer, title, model, price_cents)
                VALUES (?, ?, ?, ?)
            """, example)
            print("Saved the listing")
        else:
            print("The listing is already saved")
    
        rows = connection.execute("""
            SELECT id,retailer,title,model,price_cents FROM listings ORDER BY id
        """).fetchall()

        print(f"Database: {DATABASE_PATH}")
        print(f"Stored listings: {len(rows)}")
    
        # Retrieve and display the stored listings.
        for row in rows:
            cents = row["price_cents"]
            #calculate back to dollar value
            price ="Unknown" if cents is None else f"${cents // 100}.{cents % 100:02d}"
            print(f"[{row['id']}] {row['retailer']} | {row['title']} | "
                f"Model: {row['model'] or 'Unknown'} | {price}")
    finally:
        #release the connection
        connection.close()

if __name__ == "__main__":
    main()