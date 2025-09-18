import psycopg2
import json

# PostgreSQL connection config — replace with your real secrets (no password123 nonsense)
db_config = {
    "host": "localhost",
    "port": 5432,
    "database": "chatlogs",
    "user": "yash",
    "password": "secret"
}

# Table to extract data from
table_name = "inference_logs"

def fetch_data_from_postgres(config, table):
    try:
        # Connect to PostgreSQL like a pro
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()

        # Execute the SQL query
        cursor.execute(f"SELECT * FROM {table};")

        # Fetch column names like a proper nerd
        colnames = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        # Convert to list of dicts for proper JSON format
        data = [dict(zip(colnames, row)) for row in rows]

        cursor.close()
        conn.close()

        return data

    except Exception as e:
        print("Well, something exploded in the database world:", e)
        return []

def export_to_json(data, filename="output.json"):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4, default=str)  # <- Boom. Fixed.
        print(f"Success: Data dumped into '{filename}' like a boss.")
    except Exception as e:
        print("Oops! JSON betrayed us:", e)


if __name__ == "__main__":
    data = fetch_data_from_postgres(db_config, table_name)
    if data:
        export_to_json(data)
    else:
        print("Zero data fetched. Check your table or stop being lazy with the table name.")
