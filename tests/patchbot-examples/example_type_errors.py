"""Example file with intentional type errors for PatchBot to fix."""

from typing import List


def add_numbers(a, b):
    """Missing type annotations."""
    return a + b


def process_list(items):
    """Missing type annotations and incorrect usage."""
    result = []
    for item in items:
        result.append(item * 2)
    return result


def get_user_info(user_id):
    """Returns user info with inconsistent return type."""
    if user_id == 1:
        return {"name": "Alice", "age": 30}
    else:
        return None


class User:
    """User class with type issues."""

    def __init__(self, name, age):
        """Missing type annotations."""
        self.name = name
        self.age = age

    def get_name(self):
        """Missing return type."""
        return self.name

    def set_age(self, age):
        """Type mismatch possible."""
        self.age = age  # Could be string or int


def calculate_total(prices: List[float]) -> float:
    """Type error in implementation."""
    total = 0
    for price in prices:
        total += price
    return str(total)  # Returns str instead of float
