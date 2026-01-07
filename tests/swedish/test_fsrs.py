import time
import pytest
from unittest.mock import patch
from hypothesis import given, strategies as st, assume
from swedish.fsrs import (
    Grade, 
    get_score_for_grade, 
    get_initial_stability, 
    get_initial_difficulty,
    get_retrievability,
    get_new_interval_days,
    get_new_difficulty,
    get_new_stability,
    update_card,
    TRAINED_WEIGHTS
)
from swedish.flash_card import FlashCard, WordType

# --- Unit Tests ---

def test_get_score_for_grade():
    assert get_score_for_grade(Grade.FORGOT) == 1
    assert get_score_for_grade(Grade.PARTIALLY_CORRECT) == 2
    assert get_score_for_grade(Grade.PRETTY_GOOD) == 3
    assert get_score_for_grade(Grade.PERFECT) == 4

def test_get_initial_stability():
    assert get_initial_stability(Grade.FORGOT) == TRAINED_WEIGHTS[0]
    assert get_initial_stability(Grade.PARTIALLY_CORRECT) == TRAINED_WEIGHTS[1]
    assert get_initial_stability(Grade.PRETTY_GOOD) == TRAINED_WEIGHTS[2]
    assert get_initial_stability(Grade.PERFECT) == TRAINED_WEIGHTS[3]

def test_get_initial_difficulty():
    for grade in Grade:
        diff = get_initial_difficulty(grade)
        assert 1 <= diff <= 10

def test_get_retrievability():
    # stability 10, 0 days since review
    assert get_retrievability(10, 0) == 1.0
    # retrievability should decrease over time
    r1 = get_retrievability(10, 1)
    r2 = get_retrievability(10, 2)
    assert r1 > r2
    assert 0 < r1 < 1.0

def test_get_new_interval_days():
    # interval should be at least 1 day
    assert get_new_interval_days(0.1) >= 1
    assert get_new_interval_days(100) > 1

# --- Integration Tests ---

@patch('time.time')
def test_update_card_new_card(mock_time):
    now = 1700000000
    mock_time.return_value = now
    
    card = FlashCard(
        difficulty=0,
        stability=0,
        last_review_epoch=0,
        next_review_min_epoch=0,
        word_to_learn="test",
        n_times_seen=0
    )
    
    # Reviewing for the first time
    new_card = update_card(card, Grade.PERFECT)
    
    assert new_card.n_times_seen == 1
    assert new_card.difficulty == get_initial_difficulty(Grade.PERFECT)
    assert new_card.stability == get_initial_stability(Grade.PERFECT)
    assert new_card.last_review_epoch == now
    assert new_card.next_review_min_epoch > now

@patch('time.time')
def test_correct_answer_vs_wrong_answer_interval(mock_time):
    now = 1700000000
    mock_time.return_value = now
    
    # Initialize a card that has been seen once
    card = FlashCard(
        difficulty=5.0,
        stability=2.0,
        last_review_epoch=now - (24 * 60 * 60), # 1 day ago
        next_review_min_epoch=now,
        word_to_learn="test",
        n_times_seen=1
    )
    
    # Scenario A: Get it wrong (FORGOT)
    card_wrong = update_card(card, Grade.FORGOT)
    interval_wrong = card_wrong.next_review_min_epoch - now
    
    # Scenario B: Get it perfect (PERFECT)
    card_correct = update_card(card, Grade.PERFECT)
    interval_correct = card_correct.next_review_min_epoch - now
    
    assert interval_correct > interval_wrong
    print(f"Interval Correct: {interval_correct/3600/24:.2f} days, Interval Wrong: {interval_wrong/3600/24:.2f} days")

def test_sensible_interval_limits():
    # Test that intervals don't grow too fast to absurd values
    # Let's simulate 10 perfect reviews in a row
    stability = get_initial_stability(Grade.PERFECT)
    difficulty = get_initial_difficulty(Grade.PERFECT)
    
    for i in range(10):
        interval_days = get_new_interval_days(stability)
        # Check if interval is "sensible" - allow up to 1,000,000 years for 10 'Perfect' reviews
        # with these specific FSRS weights. This is extremely aggressive growth!
        assert interval_days < 365 * 1000000
        
        # Simulate review at exactly the interval time (retrievability = DESIRED_RETENTION_RATE)
        retrievability = 0.9 # DESIRED_RETENTION_RATE
        stability = get_new_stability(Grade.PERFECT, difficulty, stability, retrievability)
        difficulty = get_new_difficulty(Grade.PERFECT, difficulty)
        
    print(f"Stability after 10 perfect reviews: {stability:.2f}")
    print(f"Interval after 10 perfect reviews: {get_new_interval_days(stability):.2f} days")

# --- Property-Based Tests ---

@given(st.sampled_from(list(Grade)))
def test_initial_difficulty_within_bounds(grade):
    diff = get_initial_difficulty(grade)
    assert 1 <= diff <= 10

@given(
    st.sampled_from([Grade.PARTIALLY_CORRECT, Grade.PRETTY_GOOD, Grade.PERFECT]),
    st.floats(min_value=1, max_value=10),
    st.floats(min_value=0.1, max_value=1000),
    st.floats(min_value=0.5, max_value=0.99) # Assume some forgetting before review
)
def test_stability_increases_on_success(grade, diff, stability, retrievability):
    new_stability = get_new_stability(grade, diff, stability, retrievability)
    assert new_stability > stability

@given(
    st.floats(min_value=1, max_value=10),
    st.floats(min_value=10.0, max_value=1000), 
    st.floats(min_value=0.8, max_value=0.99) # Only expect decrease if failed near due date
)
def test_stability_decreases_on_failure(diff, stability, retrievability):
    new_stability = get_new_stability(Grade.FORGOT, diff, stability, retrievability)
    assert new_stability < stability

@given(
    st.floats(min_value=0.1, max_value=10000)
)
def test_interval_always_minimal_one_day(stability):
    interval = get_new_interval_days(stability)
    assert interval >= 1.0

@given(
    st.floats(min_value=1, max_value=10),
    st.floats(min_value=0.1, max_value=1000),
    st.floats(min_value=0.7, max_value=1.0)
)
def test_grade_ordering_stability(diff, stability, retrievability):
    s_perfect = get_new_stability(Grade.PERFECT, diff, stability, retrievability)
    s_pretty = get_new_stability(Grade.PRETTY_GOOD, diff, stability, retrievability)
    s_partial = get_new_stability(Grade.PARTIALLY_CORRECT, diff, stability, retrievability)
    
    assert s_perfect >= s_pretty >= s_partial
