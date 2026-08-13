"""Booking agent prompts — natural language instructions for the LLM.

These prompts describe the booking flow in human-readable steps.
The LLM reads the live DOM and decides what to click — NO hardcoded
selectors. This is what makes the agent resilient to UI changes.

The prompts are structured as task templates that get filled with
specific sport/slot/credential details at runtime.
"""

from __future__ import annotations

# ─── Main Booking Task Prompt ──────────────────────────────────────────────────

BOOKING_TASK_PROMPT = """You are an automated sports facility booking agent for the MIT-WPU sports portal.

Your goal is to book the following:
- **Sport**: {sport}
- **Target Slot**: {slot_time}
- **Website**: {website_url}

Follow these steps precisely:

## Step 1: Login
1. Navigate to {website_url}
2. Find the login form on the page
3. Enter the email: {username}
4. Enter the password: {password}
5. Click the login/sign-in button
6. Wait for the dashboard to load — verify you see the main portal page

## Step 2: Navigate to Sports
1. Look for a "Sports" link, menu item, or navigation element
2. Click on it to go to the sports facilities page
3. Wait for the sports list/cards to load

## Step 3: Find the Sport
1. If there is a search bar, type "{sport}" to filter results
2. Otherwise, scroll through the available sports to find "{sport}"
3. Click on the "{sport}" card or link
4. Look for a "View Slots" or "Book Now" button and click it

## Step 4: Select the Slot
1. Look for the time slot that matches "{slot_time}"
2. If the slot is available, click on it or click "View Spots" / "Book"
3. If the exact slot "{slot_time}" is not available, try these fallback slots in order: {fallback_slots}
4. If a spot selection screen appears, select any available spot

## Step 5: Confirm Booking
1. If there are terms and conditions, accept/check them
2. Click the "Confirm" or "Book" or "Submit" button
3. Wait for a confirmation message

## Important Rules:
- Do NOT hardcode any CSS selectors — look at the actual page content
- If a page is loading, wait for it to finish before interacting
- If you encounter a CAPTCHA, take a screenshot and report it
- If the slot shows "Full" or "Unavailable", report it and try fallback slots
- If login fails, take a screenshot and report the error
- Take a screenshot after each major step for debugging
"""

# ─── Fallback Slot Prompt ──────────────────────────────────────────────────────

FALLBACK_SLOT_PROMPT = """The primary slot "{primary_slot}" is not available.

Try booking one of these fallback slots instead (in priority order):
{fallback_slots}

Go back to the slot selection screen and try each fallback slot.
If a fallback slot is available, book it and report which slot was booked.
If none are available, report that all slots are full.
"""

# ─── Verification Prompt ───────────────────────────────────────────────────────

VERIFY_BOOKING_PROMPT = """Check if the booking was successful.

Look for:
- A confirmation message (e.g., "Booking confirmed", "Successfully booked")
- A booking reference or ID
- A confirmation email notification
- The booked slot appearing in "My Bookings" or similar section

Report what you see on the screen. Include any confirmation details.
"""


def build_booking_prompt(
    sport: str,
    slot_time: str,
    website_url: str,
    username: str,
    password: str,
    fallback_slots: list[str] | None = None,
) -> str:
    """Build the complete booking task prompt with specific details.

    Args:
        sport: Sport name as shown on the portal
        slot_time: Target slot time string
        website_url: Portal URL
        username: Decrypted username/email
        password: Decrypted password
        fallback_slots: Optional list of backup slot times

    Returns:
        Formatted prompt string ready for the agent
    """
    fallback_str = (
        "\n".join(f"  {i+1}. {slot}" for i, slot in enumerate(fallback_slots))
        if fallback_slots
        else "  (no fallback slots configured)"
    )

    return BOOKING_TASK_PROMPT.format(
        sport=sport,
        slot_time=slot_time,
        website_url=website_url,
        username=username,
        password=password,
        fallback_slots=fallback_str,
    )
