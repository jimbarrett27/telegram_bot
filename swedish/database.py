import sqlite3
import time
from typing import List, Optional
from swedish.flash_card import FlashCard, WordType

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
                word_type TEXT,
                n_times_seen INTEGER,
                difficulty REAL,
                stability REAL,
                last_review_epoch INTEGER,
                next_review_min_epoch INTEGER
            )
        ''')
        # Simple migration for existing DB
        try:
            conn.execute('ALTER TABLE flashcards ADD COLUMN word_type TEXT')
        except sqlite3.OperationalError:
            pass

        # Ensure all FSRS columns exist
        fsrs_columns = {
            "n_times_seen": "INTEGER DEFAULT 0",
            "difficulty": "REAL DEFAULT 0.0",
            "stability": "REAL DEFAULT 0.0",
            "last_review_epoch": "INTEGER DEFAULT 0",
            "next_review_min_epoch": "INTEGER DEFAULT 0"
        }
        for col, col_type in fsrs_columns.items():
            try:
                conn.execute(f'ALTER TABLE flashcards ADD COLUMN {col} {col_type}')
            except sqlite3.OperationalError:
                pass
            
    conn.close()

def add_card(word: str, word_type: WordType = WordType.UNKNOWN):
    conn = get_db_connection()
    try:
        with conn:
            conn.execute('''
                INSERT INTO flashcards (word_to_learn, word_type, n_times_seen, difficulty, stability, last_review_epoch, next_review_min_epoch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (word, word_type.name, 0, 0.0, 0.0, 0, 0))
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def get_card(word: str) -> Optional[FlashCard]:
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM flashcards WHERE word_to_learn = ?', (word,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        val = row['word_type']
        # Handle existing rows or nulls defaults
        w_type = WordType[val] if val else WordType.UNKNOWN
        
        return FlashCard(
            word_to_learn=row['word_to_learn'],
            word_type=w_type,
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
                next_review_min_epoch = ?,
                word_type = ?
            WHERE word_to_learn = ?
        ''', (
            card.n_times_seen,
            card.difficulty,
            card.stability,
            card.last_review_epoch,
            card.next_review_min_epoch,
            card.word_type.name,
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
        val = row['word_type']
        w_type = WordType[val] if val else WordType.UNKNOWN
        
        cards.append(FlashCard(
            word_to_learn=row['word_to_learn'],
            word_type=w_type,
            n_times_seen=row['n_times_seen'],
            difficulty=row['difficulty'],
            stability=row['stability'],
            last_review_epoch=row['last_review_epoch'],
            next_review_min_epoch=row['next_review_min_epoch']
        ))
    return cards

def get_next_due_card() -> Optional[FlashCard]:
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM flashcards ORDER BY next_review_min_epoch ASC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        val = row['word_type']
        w_type = WordType[val] if val else WordType.UNKNOWN
        
        return FlashCard(
            word_to_learn=row['word_to_learn'],
            word_type=w_type,
            n_times_seen=row['n_times_seen'],
            difficulty=row['difficulty'],
            stability=row['stability'],
            last_review_epoch=row['last_review_epoch'],
            next_review_min_epoch=row['next_review_min_epoch']
        )
    return None

def get_all_words() -> List[str]:
    conn = get_db_connection()
    cursor = conn.execute('SELECT word_to_learn FROM flashcards')
    rows = cursor.fetchall()
    conn.close()
    return [row['word_to_learn'] for row in rows]

def populate_db():
    from util.constants import REPO_ROOT

    data_dir = REPO_ROOT / "swedish/data"
    
    files_map = {
        "verbs.txt": WordType.VERB,
        "nouns.txt": WordType.NOUN,
        "adjectives.txt": WordType.ADJECTIVE
    }

    print(f"Populating database from {data_dir}...")
    
    existing_words = set(get_all_words())
    print(f"Found {len(existing_words)} existing words in DB.")

    for filename, word_type in files_map.items():
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"Warning: {filename} not found at {filepath}")
            continue
            
        with open(filepath, "r") as f:
            count = 0
            skipped = 0
            for line in f:
                word = line.strip()
                if word:
                    if word in existing_words:
                        skipped += 1
                        continue
                        
                    add_card(word, word_type)
                    count += 1
            print(f"Added {count} {word_type.name.lower()}s from {filename} (skipped {skipped} existing)")


def count_cards() -> int:
    conn = get_db_connection()
    cursor = conn.execute('SELECT COUNT(*) FROM flashcards')
    count = cursor.fetchone()[0]
    conn.close()
    return count
