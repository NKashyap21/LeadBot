import sqlite3

def is_duplicate(conn:sqlite3.Connection,linked_in:str) -> bool:
    cursor = conn.cursor() 
    cursor.execute(
        "SELECT * FROM leads_seen WHERE linkedin_url=?",
        (linked_in,)
    )

    return cursor.fetchone() is not None

def mark_seen(conn:sqlite3.Connection,linked_in:str):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO leads_seen (linkedin_url) VALUES (?)",
        (linked_in,)
    )

    conn.commit()