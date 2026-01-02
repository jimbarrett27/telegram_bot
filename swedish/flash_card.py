from dataclasses import dataclass

@dataclass
class FlashCard:

    difficulty: float
    stability: float
    last_review_epoch: int
    next_review_min_epoch: int
    word_to_learn: str
    n_times_seen: int = 0
    