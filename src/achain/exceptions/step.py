"""
All exceptions related to failed steps within a chain
"""


class StepError(Exception):
    """
    Indicates that an error occured during a step within a chain operation
    """