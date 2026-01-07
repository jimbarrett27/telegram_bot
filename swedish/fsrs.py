from enum import Enum
import math
import time
from swedish.flash_card import FlashCard


F = 19/81
C = -0.5
DESIRED_RETENTION_RATE = 0.9

TRAINED_WEIGHTS = [
    0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925,
    1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621,
]

class Grade(Enum):
    FORGOT = 0
    PARTIALLY_CORRECT = 1
    PRETTY_GOOD = 2
    PERFECT = 3



def get_score_for_grade(grade: Grade) -> int:
    
    match grade:
        case Grade.FORGOT:
            return 1
        case Grade.PARTIALLY_CORRECT:
            return 2
        case Grade.PRETTY_GOOD:
            return 3
        case Grade.PERFECT:
            return 4

def get_retrievability(stability: float, time_since_review_days: float) -> float:

    retrievability = (1 + (F*time_since_review_days/stability))**C

    return retrievability

def get_new_interval_days(stability: float):

    r_to_1_over_c = DESIRED_RETENTION_RATE**(1/C)
    t1 = stability / F
    t2 = r_to_1_over_c - 1

    return max(t1 * t2, 1)

def get_initial_stability(grade: Grade):

    match grade:
        case Grade.FORGOT:
            return TRAINED_WEIGHTS[0]
        case Grade.PARTIALLY_CORRECT:
            return TRAINED_WEIGHTS[1]
        case Grade.PRETTY_GOOD:
            return TRAINED_WEIGHTS[2]
        case Grade.PERFECT:
            return TRAINED_WEIGHTS[3]


def get_new_stability_success(grade: Grade, difficulty: float, stability: float, retrievability: float):

    difficulty_factor = 11 - difficulty
    stability_factor = stability ** (-1*TRAINED_WEIGHTS[9])
    retrievability_factor = -1 + (math.exp((1-retrievability)*TRAINED_WEIGHTS[10]))

    hard_penalty = TRAINED_WEIGHTS[15] if grade == Grade.PARTIALLY_CORRECT else 1
    easy_bonus = TRAINED_WEIGHTS[16] if grade == Grade.PERFECT else 1

    stability_scaling_factor = 1 + (difficulty_factor*stability_factor*retrievability_factor*hard_penalty*easy_bonus*math.exp(TRAINED_WEIGHTS[8]))

    return stability * stability_scaling_factor

def get_new_stability_failure(difficulty: float, stability: float, retrievability: float):

    difficulty_factor = difficulty ** (-1*TRAINED_WEIGHTS[12])
    stability_factor = ((stability+1)**TRAINED_WEIGHTS[13]) - 1
    retrievability_factor = math.exp(TRAINED_WEIGHTS[14]*(1-retrievability))

    return difficulty_factor * stability_factor * retrievability_factor * TRAINED_WEIGHTS[11]

def get_new_stability(grade: Grade, difficulty: float, stability: float, retrievability: float):

    if grade == Grade.FORGOT:
        return get_new_stability_failure(difficulty, stability, retrievability)
    else:
        return get_new_stability_success(grade, difficulty, stability, retrievability)

def get_initial_difficulty(grade: Grade):

    score = get_score_for_grade(grade)

    t1 = TRAINED_WEIGHTS[4]
    t2 = (-1)*math.exp((score-1)*TRAINED_WEIGHTS[5])

    difficulty = t1 + t2 + 1

    if difficulty < 1:
        return 1
    elif difficulty > 10:
        return 10
    else:
        return difficulty

def get_new_difficulty(grade: Grade, difficulty: float):

    score = get_score_for_grade(grade)

    delta_d = (-1)*TRAINED_WEIGHTS[6]*(score - 3)
    d_prime = difficulty + (delta_d*((10-difficulty)/9))
    d_double_prime_t1 = TRAINED_WEIGHTS[7] * get_initial_difficulty(Grade.PERFECT)
    d_double_prime_t2 = (1 - TRAINED_WEIGHTS[7])*d_prime

    return d_double_prime_t1 + d_double_prime_t2

def update_card(card: FlashCard, grade: Grade):

    current_epoch = int(time.time())

    if card.n_times_seen == 0:

        new_difficulty = get_initial_difficulty(grade)
        new_stability = get_initial_stability(grade)

    else:
        days_since_last_review = (current_epoch - card.last_review_epoch) / (60*60*24)

        retrievability = get_retrievability(card.stability, days_since_last_review)
        new_difficulty = get_new_difficulty(grade, card.difficulty)
        new_stability = get_new_stability(grade, card.difficulty, card.stability, retrievability)

    new_interval_seconds = get_new_interval_days(new_stability) * 24 * 60 * 60

    return FlashCard(
        n_times_seen=card.n_times_seen + 1,
        difficulty=new_difficulty,
        stability=new_stability,
        last_review_epoch=current_epoch,
        next_review_min_epoch=current_epoch + new_interval_seconds,
        word_to_learn=card.word_to_learn
    )




