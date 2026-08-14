"""Booking agent prompts — natural language instructions for the LLM.

These prompts describe the booking flow based on the ACTUAL portal UI
(sports.mitwpu.edu.in) as mapped on 14-Aug-2026:

Portal flow:
  Login → Dashboard → Click "Book now" → Sports grid → Click "View Slots"
  → Slots page → Click "View Spots" → Select spot → Confirm

The LLM reads the live DOM and decides what to click — NO hardcoded
selectors. This is what makes the agent resilient to UI changes.
"""

from __future__ import annotations

# ─── Main Booking Task Prompt ──────────────────────────────────────────────────

BOOKING_TASK_PROMPT = """You are an automated sports facility booking agent for the MIT-WPU Dronacharya Sports Complex portal.

Your goal is to book the following:
- **Sport**: {sport}
- **Target Slot**: {slot_time}
- **Website**: {website_url}

Follow these steps precisely:

## Step 1: Login
1. Navigate to {website_url}/login
2. Find the email input field and type: {username}
3. Find the password input field and type: {password}
4. Click the "Login" button
5. Wait for the page to load — you should see the dashboard with "MIT WPU's Dronacharya Sports Complex" heading

## Step 2: Navigate to Sports
1. On the dashboard, find and click the "Book now" button (it's a dark/black button)
2. Wait for the sports listing page to load
3. You should see a grid of sport cards with titles like "Swimming Pool", "Table_Tennis - 1", etc.

## Step 3: Find the Sport
1. Look through the grid of sport cards for one titled "{sport}"
2. You may need to scroll down to find it — the sports are in a grid layout
3. Each card has the sport name at the top, an image, "Available" / "Book Now" labels, and a "View Slots" button at the bottom
4. Click the "View Slots" button on the "{sport}" card

## Step 4: Select the Slot
1. You should now see "Available Slots" heading with the sport name below it
2. Slots are shown as cards with time ranges (e.g., "10:00 AM – 10:50 AM")
3. Each slot shows: time range, target group (e.g., "Open to All"), spots available (e.g., "3/4 spots available"), and a status
4. Find the slot matching "{slot_time}"
5. If the slot is available (not "Ended"), click the "View Spots" button on that slot card
6. If the target slot is full or ended, try these fallback slots in order: {fallback_slots}

## Step 5: Select a Spot and Confirm
1. On the spots page, you should see individual spots/seats available
2. Select any available spot
3. If there are terms and conditions, accept/check them
4. Click the confirm/book button
5. Wait for a confirmation message

## Important Rules:
- Do NOT hardcode any CSS selectors — look at the actual visible text and elements
- If a page is loading (button says "Please wait"), wait for it to finish
- The slots page shows times like "10:00 AM – 10:50 AM" — match the format exactly
- If you see a red "Ended" badge on all slots, it means booking hours are over — report this
- If you see "0/4 spots available" that means the slot is full — try fallback slots
- Take a screenshot after each major step for debugging
"""

# ─── Fallback Slot Prompt ──────────────────────────────────────────────────────

FALLBACK_SLOT_PROMPT = """The primary slot "{primary_slot}" is not available (full or ended).

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
- The booked slot appearing in "My Bookings" (click the profile avatar → "My Bookings")

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
        sport: Sport name exactly as shown on the portal (e.g., "Swimming Pool", "Table_Tennis - 5")
        slot_time: Target slot time exactly as shown (e.g., "10:00 AM – 10:50 AM")
        website_url: Portal URL (default: https://sports.mitwpu.edu.in)
        username: Decrypted email
        password: Decrypted password
        fallback_slots: Optional list of backup slot time strings

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
