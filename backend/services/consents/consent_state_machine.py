"""
Consent State Machine

Pure Python module with no MongoDB dependencies.
Defines valid states, transitions, purposes, and rejection codes for consent lifecycle.
"""

# Valid consent statuses
VALID_STATUSES = {
    "AWAITING_AUTHORISATION",
    "AUTHORISED",
    "CONSUMED",
    "REJECTED",
    "REVOKED",
    "EXPIRED"
}

# Valid state transitions: from_status -> [allowed_to_statuses]
VALID_TRANSITIONS = {
    "AWAITING_AUTHORISATION": ["AUTHORISED", "REJECTED"],
    "AUTHORISED": ["CONSUMED", "REVOKED"],
}

# Terminal statuses (no further transitions allowed)
TERMINAL_STATUSES = {"REJECTED", "CONSUMED", "REVOKED", "EXPIRED"}

# Valid consent purposes
VALID_PURPOSES = {
    "LOAN_PORTABILITY",
    "CREDIT_CARD_PORTABILITY",
    "FINANCIAL_ADVICE"
}

# Valid rejection codes
REJECTION_CODES = {
    "CUSTOMER_MANUALLY_REJECTED",
    "CONSENT_EXPIRED",
    "CUSTOMER_MANUALLY_REVOKED",
    "CONSENT_TECHNICAL_ISSUE",
    "INTERNAL_SECURITY_REASON",
}


def validate_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if a state transition is allowed.

    Args:
        current_status (str): The current status of the consent.
        new_status (str): The target status to transition to.

    Returns:
        bool: True if transition is valid.

    Raises:
        ValueError: If the transition is not allowed, with a descriptive message.
    """
    # Check if current status is valid
    if current_status not in VALID_STATUSES:
        raise ValueError(f"Invalid current status: '{current_status}'. Valid statuses are: {VALID_STATUSES}")

    # Check if new status is valid
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid target status: '{new_status}'. Valid statuses are: {VALID_STATUSES}")

    # Check if current status is terminal
    if current_status in TERMINAL_STATUSES:
        raise ValueError(
            f"Cannot transition from terminal status '{current_status}'. "
            f"Terminal statuses are: {TERMINAL_STATUSES}"
        )

    # Check if transition is allowed
    allowed_transitions = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_transitions:
        raise ValueError(
            f"Invalid transition: '{current_status}' -> '{new_status}'. "
            f"Allowed transitions from '{current_status}' are: {allowed_transitions}"
        )

    return True


def is_terminal(status: str) -> bool:
    """
    Check if a status is a terminal state (no further transitions possible).

    Args:
        status (str): The status to check.

    Returns:
        bool: True if the status is terminal, False otherwise.
    """
    return status in TERMINAL_STATUSES


def validate_purpose(purpose: str) -> bool:
    """
    Validate if a purpose is valid.

    Args:
        purpose (str): The purpose to validate.

    Returns:
        bool: True if purpose is valid.

    Raises:
        ValueError: If the purpose is not valid.
    """
    if purpose not in VALID_PURPOSES:
        raise ValueError(f"Invalid purpose: '{purpose}'. Valid purposes are: {VALID_PURPOSES}")
    return True


def validate_rejection_code(code: str) -> bool:
    """
    Validate if a rejection code is valid.

    Args:
        code (str): The rejection code to validate.

    Returns:
        bool: True if code is valid.

    Raises:
        ValueError: If the rejection code is not valid.
    """
    if code not in REJECTION_CODES:
        raise ValueError(f"Invalid rejection code: '{code}'. Valid codes are: {REJECTION_CODES}")
    return True


def can_retrieve_data(status: str) -> bool:
    """
    Check if data can be retrieved with the given consent status.
    Only AUTHORISED consents allow data retrieval.

    Args:
        status (str): The consent status.

    Returns:
        bool: True if data retrieval is allowed.
    """
    return status == "AUTHORISED"
