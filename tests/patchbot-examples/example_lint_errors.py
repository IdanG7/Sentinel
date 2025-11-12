"""Example file with intentional linting errors for PatchBot to fix."""

import os
import sys
from typing import Optional


def example_function(x, y):
    """Function with linting issues."""

    # Unused import (os)
    # Missing type annotations
    # Undefined variable
    result = x + y + undefined_var  # noqa: F821

    # Unnecessary pass
    if True:
        pass

    # Bare except
    try:
        value = 1 / 0
    except:
        print("Error occurred")

    return result


# Unused function
def unused_function():
    """This function is never called."""
    return 42


# Global variable (not following conventions)
globalVariable = "should be GLOBAL_VARIABLE"


class ExampleClass:
    """Example class with issues."""

    def method_with_issues(self, param):
        """Method with type issues."""
        # Missing return type
        # Ambiguous variable names
        a = param
        b = a + 1
        c = b * 2
        return c
