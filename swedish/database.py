import sqlite3
import time
from typing import List, Optional
from swedish.flash_card import FlashCard

DB_NAME = "flashcards.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS flashcards (
                word_to_learn TEXT PRIMARY KEY,
                n_times_seen INTEGER,
                difficulty REAL,
                stability REAL,
                last_review_epoch INTEGER,
                next_review_min_epoch INTEGER
            )
        ''')
    conn.close()

def add_card(word: str):
    conn = get_db_connection()
    # Default initial values for FSRS (can be tuned or taken from constants if available)
    # Using defaults that make sense or placeholders that will be updated on first review.
    # However, FlashCard dataclass doesn't specify defaults for these, 
    # so we should probably initialize them to "new card" state.
    # We'll use 0 or initial values. 
    # Let's assume a new card hasn't been seen.
    
    # Based on fsrs.py updates, initial difficulty/stability depend on the first grade.
    # We will store initial "zero" state.
    
    try:
        with conn:
            conn.execute('''
                INSERT INTO flashcards (word_to_learn, n_times_seen, difficulty, stability, last_review_epoch, next_review_min_epoch)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (word, 0, 0.0, 0.0, 0, 0))
    except sqlite3.IntegrityError:
        # Card already exists
        pass
    finally:
        conn.close()

def get_card(word: str) -> Optional[FlashCard]:
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM flashcards WHERE word_to_learn = ?', (word,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return FlashCard(
            word_to_learn=row['word_to_learn'],
            n_times_seen=row['n_times_seen'],
            difficulty=row['difficulty'],
            stability=row['stability'],
            last_review_epoch=row['last_review_epoch'],
            next_review_min_epoch=row['next_review_min_epoch']
        )
    return None

def update_card(card: FlashCard):
    conn = get_db_connection()
    with conn:
        conn.execute('''
            UPDATE flashcards
            SET n_times_seen = ?,
                difficulty = ?,
                stability = ?,
                last_review_epoch = ?,
                next_review_min_epoch = ?
            WHERE word_to_learn = ?
        ''', (
            card.n_times_seen,
            card.difficulty,
            card.stability,
            card.last_review_epoch,
            card.next_review_min_epoch,
            card.word_to_learn
        ))
    conn.close()

def get_due_cards() -> List[FlashCard]:
    current_epoch = int(time.time())
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM flashcards WHERE next_review_min_epoch <= ?', (current_epoch,))
    rows = cursor.fetchall()
    conn.close()
    
    cards = []
    for row in rows:
        cards.append(FlashCard(
            word_to_learn=row['word_to_learn'],
            n_times_seen=row['n_times_seen'],
            difficulty=row['difficulty'],
            stability=row['stability'],
            last_review_epoch=row['last_review_epoch'],
            next_review_min_epoch=row['next_review_min_epoch']
        ))
    return cards

def get_all_words() -> List[str]:
    conn = get_db_connection()
    cursor = conn.execute('SELECT word_to_learn FROM flashcards')
    rows = cursor.fetchall()
    conn.close()
    return [row['word_to_learn'] for row in rows]

def count_cards() -> int:
    conn = get_db_connection()
    cursor = conn.execute('SELECT COUNT(*) FROM flashcards')
    count = cursor.fetchone()[0]
    conn.close()
    return count
