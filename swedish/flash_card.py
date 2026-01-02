from dataclasses import dataclass

@dataclass
class FlashCard:

    n_times_seen: int = 0
    difficulty: float
    stability: float
    last_review_epoch: int
    next_review_min_epoch: int

    word_to_learn: str
    