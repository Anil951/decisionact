"""Flight-desk agent built with DecisionAct: tools, intents, outcomes. A harder agent than
order_agent.py: seven tools, nine intents, inputs of many kinds (cities, dates, a passenger name,
cabin, kilograms, seats), values carried from one turn to the next (the date of a search is
the date of the booking), lists to pick from, and rules in the data (fare types, change fee,
refund, seat cabins, baggage limits).
Run from the project folder: python -m examples.flight_desk_agent"""
import datetime as dt
import re


import os
from pathlib import Path

from dotenv import load_dotenv

from decisionact import Agent, Intent, Outcome, Param, tool
# from decisionact.checkpoint import SqliteCheckpointer
from decisionact.models import CloudflareModel, SystemOneModel
from decisionact.memory import ConversationBufferMemory


# ======================= FAKE DATA =======================
TODAY = dt.date.today()

FLIGHTS = {  # economy fare in INR; business costs twice as much
    "FL101": {"origin": "Delhi", "destination": "Mumbai", "departs": "06:00", "fare": 4500, "fare_type": "saver"},
    "FL102": {"origin": "Delhi", "destination": "Mumbai", "departs": "09:30", "fare": 6200, "fare_type": "flex"},
    "FL103": {"origin": "Delhi", "destination": "Mumbai", "departs": "18:45", "fare": 5200, "fare_type": "saver"},
    "FL201": {"origin": "Mumbai", "destination": "Delhi", "departs": "07:15", "fare": 4800, "fare_type": "saver"},
    "FL202": {"origin": "Mumbai", "destination": "Delhi", "departs": "20:00", "fare": 6500, "fare_type": "flex"},
    "FL301": {"origin": "Delhi", "destination": "Bengaluru", "departs": "08:00", "fare": 5600, "fare_type": "saver"},
    "FL302": {"origin": "Delhi", "destination": "Bengaluru", "departs": "14:20", "fare": 7400, "fare_type": "flex"},
    "FL401": {"origin": "Bengaluru", "destination": "Chennai", "departs": "11:00", "fare": 3200, "fare_type": "saver"},
    "FL501": {"origin": "Mumbai", "destination": "Hyderabad", "departs": "10:30", "fare": 3900, "fare_type": "flex"},
    "FL502": {"origin": "Hyderabad", "destination": "Kolkata", "departs": "16:40", "fare": 4400, "fare_type": "saver"},
}

BOOKINGS = {
    "BK1001": {"flight_id": "FL101", "passenger_name": "Asha Rao", "route": "Delhi to Mumbai",
               "date": (TODAY + dt.timedelta(days=30)).isoformat(), "seat_class": "economy", "fare_type": "saver", "price": 4500,
               "status": "confirmed", "baggage_kg": 0, "seat": None},
    "BK1002": {"flight_id": "FL302", "passenger_name": "Ravi Kumar", "route": "Delhi to Bengaluru",
               "date": (TODAY + dt.timedelta(days=36)).isoformat(), "seat_class": "business", "fare_type": "flex", "price": 14800,
               "status": "confirmed", "baggage_kg": 0, "seat": None},
    "BK1003": {"flight_id": "FL201", "passenger_name": "Meera Shah", "route": "Mumbai to Delhi",
               "date": (TODAY - dt.timedelta(days=15)).isoformat(), "seat_class": "economy", "fare_type": "saver", "price": 4800,
               "status": "completed", "baggage_kg": 5, "seat": "14C"},
}

TAKEN_SEATS = {"3A", "7C", "12A", "12B"}
CITIES = {"delhi": "Delhi", "mumbai": "Mumbai", "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
          "chennai": "Chennai", "hyderabad": "Hyderabad", "kolkata": "Kolkata", "goa": "Goa"}
CITY = "(?:delhi|mumbai|bengaluru|bangalore|chennai|hyderabad|kolkata|goa)"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DATE = (r"(?i)\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
        r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\b"
        r"|\b\d{4}-\d{2}-\d{2}\b")


def _date(text):
    """'14 Nov', '14th November', 'Nov 14' or '2026-11-14' -> a date, or None. Without a year it is
    the next such day from TODAY."""
    t = str(text).strip().lower()
    try:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
        if m:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)", t)
        if m:
            day, name = int(m[1]), m[2]
        else:
            m = re.fullmatch(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?", t)
            if not m:
                return None
            name, day = m[1], int(m[2])
        month = MONTHS.index(name[:3]) + 1
        d = dt.date(TODAY.year, month, day)
        return d if d >= TODAY else dt.date(TODAY.year + 1, month, day)
    except ValueError:
        return None


def _future_date(text):
    """(ISO date, None) or (None, the reason it is not usable)."""
    d = _date(text)
    if d is None:
        return None, f"'{text}' is not a valid date"
    if d < TODAY:
        return None, f"{d.isoformat()} is in the past"
    return d.isoformat(), None


def _booking(booking_id):
    bid = str(booking_id).upper()
    return (bid, BOOKINGS[bid]) if bid in BOOKINGS else (bid, None)


# ======================= TOOLS =======================
BOOKING_ID = Param(desc="BK followed by four digits, e.g. BK1001", pattern=r"(?i)\bBK\d{4}\b")


@tool(origin=Param(desc="the city the trip starts from",
                   pattern=rf"(?i)\b{CITY}\b(?=\s+to\b)|(?<=\bfrom\s){CITY}\b"),
      destination=Param(desc="the city the trip goes to", pattern=rf"(?i)(?<=\bto\s){CITY}\b"),
      date=Param(desc="the travel date, like 14 Nov or 2026-11-14", pattern=DATE),
      passengers=Param(desc="the number of passengers, a single digit from 1 to 9", pattern=r"\b[1-9]\b"))
def search_flights(origin: str, destination: str, date: str, passengers: str) -> dict:
    """Search flights between two cities (Delhi, Mumbai, Bengaluru, Chennai, Hyderabad, Kolkata,
    Goa) on a date for a number of passengers. Returns the flights with their ID, route,
    departure time and economy/business fares, or an empty list when there are none."""
    o, d = CITIES.get(str(origin).lower()), CITIES.get(str(destination).lower())
    iso, error = _future_date(date)
    if error:
        return {"error": error}
    if not o or not d or o == d:
        return {"error": "origin and destination must be two different known cities"}
    found = [{"flight_id": f, "route": f"{x['origin']} to {x['destination']}", "departs": x["departs"],
              "fare": f"economy {x['fare']} / business {2 * x['fare']} ({x['fare_type']})"}
             for f, x in FLIGHTS.items() if x["origin"] == o and x["destination"] == d]
    return {"flights": found, "count": len(found), "origin": o, "destination": d, "date": iso,
            "passengers": int(passengers)}


@tool(flight_id=Param(desc="FL followed by three digits, e.g. FL102", pattern=r"(?i)\bFL\d{3}\b", optional=True),
      date=Param(desc="the travel date of the flight, like 14 Nov or 2026-11-14", pattern=DATE),
      passenger_name=Param(desc="the passenger's full name as the user wrote it, e.g. Asha Rao"),
      seat_class=Param(desc="the cabin the user wants",
                       options={"economy": "The user wants an economy seat.",
                                "business": "The user wants a business class seat."}))
def book_flight(date: str, passenger_name: str, seat_class: str, flight_id: str = None) -> dict:
    """Book one seat on a flight (flight ID from a search) on a date for a named passenger in
    economy or business. Returns the new booking with its booking ID and price."""
    if flight_id is None:
        return {"error": "no flight was chosen"}
    fid = str(flight_id).upper()
    if fid not in FLIGHTS:
        return {"error": f"flight {fid} not found"}
    iso, error = _future_date(date)
    if error:
        return {"error": error}
    f = FLIGHTS[fid]
    bid = f"BK{1001 + len(BOOKINGS)}"
    BOOKINGS[bid] = {"flight_id": fid, "passenger_name": passenger_name,
                     "route": f"{f['origin']} to {f['destination']}", "date": iso, "seat_class": seat_class,
                     "fare_type": f["fare_type"], "price": f["fare"] * (2 if seat_class == "business" else 1),
                     "status": "confirmed", "baggage_kg": 0, "seat": None}
    return {"booking_id": bid, **BOOKINGS[bid]}


@tool(booking_id=Param(desc=BOOKING_ID.desc, pattern=BOOKING_ID.pattern, optional=True))
def get_booking(booking_id: str = None) -> dict:
    """Look up a booking: passenger, route, date, cabin, fare type, status (confirmed, cancelled
    or completed), baggage and seat. With a booking ID: returns that booking. Without one:
    returns all bookings. Needed to answer questions and to check a booking before changing it."""
    if booking_id is None:
        return {"bookings": [{"booking_id": b, "passenger_name": x["passenger_name"], "route": x["route"],
                              "date": x["date"], "status": x["status"]} for b, x in BOOKINGS.items()]}
    bid, b = _booking(booking_id)
    return {"error": f"booking {bid} not found"} if b is None else {"booking_id": bid, **b}


@tool(booking_id=BOOKING_ID,
      new_date=Param(desc="the new travel date, like 20 Nov or 2026-11-20", pattern=DATE))
def change_flight(booking_id: str, new_date: str) -> dict:
    """Move a confirmed booking to another date. A saver fare has a change fee of 3000, a flex
    fare is free to change. Returns the new date and the fee."""
    bid, b = _booking(booking_id)
    if b is None:
        return {"error": f"booking {bid} not found"}
    if b["status"] != "confirmed":
        return {"error": f"booking {bid} is {b['status']} and can't be changed", "route": b["route"],
                "status": b["status"]}
    iso, error = _future_date(new_date)
    if error:
        return {"error": error}
    b["date"] = iso
    return {"booking_id": bid, "route": b["route"], "new_date": iso, "fare_type": b["fare_type"],
            "fee": 3000 if b["fare_type"] == "saver" else 0}


@tool(booking_id=BOOKING_ID,
      reason=Param(desc="why the user cancels, as one of four categories: changed plans, found a "
                        "better fare, emergency, other",
                   options={"changed plans": "The user's plans or schedule changed, or they no longer travel.",
                            "found a better fare": "The user found a cheaper or better flight elsewhere.",
                            "emergency": "A medical or family emergency.",
                            "other": "The user gives any other reason."}))
def cancel_booking(booking_id: str, reason: str) -> dict:
    """Cancel a confirmed booking, with the reason. A flex fare is refunded in full, a saver fare
    only 20%. Returns the refund."""
    bid, b = _booking(booking_id)
    if b is None:
        return {"error": f"booking {bid} not found"}
    if b["status"] != "confirmed":
        return {"error": f"booking {bid} is {b['status']} and can't be cancelled", "route": b["route"],
                "status": b["status"]}
    b["status"] = "cancelled"
    refund = b["price"] if b["fare_type"] == "flex" else round(b["price"] * 0.2)
    return {"booking_id": bid, "route": b["route"], "status": "cancelled", "fare_type": b["fare_type"],
            "refund": refund, "reason": reason}


@tool(booking_id=BOOKING_ID,
      kg=Param(desc="the extra baggage in kilograms, like 10 kg", pattern=r"(?i)\b\d{1,2}\s?kgs?\b"))
def add_baggage(booking_id: str, kg: str) -> dict:
    """Add extra baggage to a confirmed booking at 400 per kg. At most 15 kg extra in economy and
    25 kg extra in business. Returns the baggage total and the fee."""
    bid, b = _booking(booking_id)
    if b is None:
        return {"error": f"booking {bid} not found"}
    if b["status"] != "confirmed":
        return {"error": f"booking {bid} is {b['status']} and can't be changed", "route": b["route"],
                "status": b["status"]}
    amount = int(re.search(r"\d+", str(kg))[0])
    limit = 25 if b["seat_class"] == "business" else 15
    if amount < 1 or b["baggage_kg"] + amount > limit:
        return {"error": f"extra baggage is limited to {limit} kg in {b['seat_class']} "
                         f"({b['baggage_kg']} kg already added)"}
    b["baggage_kg"] += amount
    return {"booking_id": bid, "route": b["route"], "kg": amount, "total_baggage_kg": b["baggage_kg"],
            "fee": 400 * amount}


@tool(booking_id=BOOKING_ID,
      seat=Param(desc="a seat like 14C: a row number and a letter A to F", pattern=r"(?i)\b\d{1,2}[A-F]\b"))
def select_seat(booking_id: str, seat: str) -> dict:
    """Pick a seat on a confirmed booking. Rows 1-5 are business, rows 6-30 are economy; the seat
    must match the booking's cabin and not be taken."""
    bid, b = _booking(booking_id)
    if b is None:
        return {"error": f"booking {bid} not found"}
    if b["status"] != "confirmed":
        return {"error": f"booking {bid} is {b['status']} and can't be changed", "route": b["route"],
                "status": b["status"]}
    s = str(seat).upper()
    row = int(s[:-1])
    if not 1 <= row <= 30:
        return {"error": f"there is no seat {s}"}
    if (row <= 5) != (b["seat_class"] == "business"):
        return {"error": f"seat {s} is not in the {b['seat_class']} cabin"}
    if s in TAKEN_SEATS:
        return {"error": f"seat {s} is already taken"}
    b["seat"] = s
    return {"booking_id": bid, "route": b["route"], "seat": s}


# ======================= INTENTS =======================
INTENTS = {
    "search_flights": Intent(
        desc="The user wants to find flights between two cities: availability, times or fares. "
             "Examples: 'flights from Delhi to Mumbai on 14 Nov', 'any flights to Chennai?', "
             "'show flights Delhi to Bengaluru for 2 people'. Also a reply that only gives a "
             "missing detail (a city, a date or the number of passengers) after the agent asked "
             "for it for a flight search. NOT booking a flight that was already chosen (that is "
             "book_flight).",
        context="Call search_flights exactly once with the origin, destination, date and number of "
                "passengers, then stop: no further tool call is needed. If it returned flights, "
                "the outcome is flights_found; if it returned an empty list, no_flights; if it "
                "returned an error, search_error.",
        tools=["search_flights"],
        outcomes=["flights_found", "no_flights", "search_error", "failed"]),
    "book_flight": Intent(
        desc="The user wants to book a flight they have chosen, by its flight ID or by picking it "
             "from the flights the agent just showed. Examples: 'book FL102', 'the second one', "
             "'the cheaper one', 'book it for Asha Rao in economy'. Also a reply that only gives "
             "the passenger name, the cabin or the date after the agent asked for it to complete "
             "a booking. NOT searching for flights (that is search_flights).",
        context="Call book_flight exactly once, then stop. The flight is the one the user names or "
                "picks from the list the agent showed; the date is the date of that search; the "
                "passenger name and the cabin (economy or business) come from the user's messages. "
                "If no flight was named or picked, still call book_flight without a flight ID; the "
                "outcome is then choose_flight. If it returned a booking, the outcome is booked; "
                "if the flight was not found, flight_not_found; any other error, book_error.",
        tools=["book_flight"],
        outcomes=["booked", "choose_flight", "flight_not_found", "book_error", "failed"]),
    "booking_status": Intent(
        desc="The user wants to know about an existing booking or see their bookings: its "
             "status, flight, date, or whether it is confirmed. Examples: 'show my bookings', "
             "'status of BK1001', 'is my flight confirmed?', 'my trip details'. Also a reply that "
             "only gives a booking ID after the agent asked which booking to look at. NOT "
             "changing or cancelling a booking (those have their own intents).",
        context="Answer with exactly ONE get_booking call, then stop. If the user's current message "
                "names a booking ID, call get_booking with it and the outcome is that booking's "
                "status (booking_confirmed, booking_cancelled or booking_completed), or not_found. "
                "If the current message names NO booking ID, call get_booking without one; it "
                "returns the list of all bookings and the outcome is booking_list. Never call "
                "get_booking twice in the same turn.",
        tools=["get_booking"],
        outcomes=["booking_confirmed", "booking_cancelled", "booking_completed", "not_found",
                  "booking_list", "failed"]),
    "change_booking": Intent(
        desc="The user wants to move an existing booking to another date: reschedule, change the "
             "date, postpone. Examples: 'move my flight to 20 Nov', 'change BK1002 to 25 Nov', "
             "'I need a different date'. Also a reply that only gives a booking ID or a new date "
             "after the agent asked for it. NOT a new booking (that is book_flight) and NOT "
             "cancelling.",
        context="Step 1: the FIRST tool call is ALWAYS get_booking, exactly once, even when the user "
                "names, picks or refers to a booking ('it', 'that booking'): until get_booking has "
                "been called this turn, the next tool is get_booking, never change_flight. If the "
                "user's current message names, picks or refers to a booking, call get_booking for "
                "it; otherwise call it without a booking ID, which returns the list of all "
                "bookings. Step 2: if get_booking returned the "
                "LIST, stop: do NOT call change_flight, the outcome is choose_booking. If it "
                "returned one booking that is cancelled or completed, stop: the outcome is "
                "booking_closed. If it returned not found, stop: not_found. If it returned one "
                "confirmed booking, call change_flight for that same booking ID with the new date; "
                "the outcome is changed, or change_error if the tool returned an error.",
        tools=["get_booking", "change_flight"],
        outcomes=["changed", "booking_closed", "not_found", "choose_booking", "change_error", "failed"]),
    "cancel_booking": Intent(
        desc="The user wants to cancel a booking or no longer travels. Examples: 'cancel my "
             "booking', 'cancel BK1001', 'I don't want to fly anymore'. Also a reply that only "
             "gives a booking ID and/or a reason after the agent asked which booking to cancel or "
             "why. NOT changing the date (that is change_booking).",
        context="Step 1: the FIRST tool call is ALWAYS get_booking, exactly once, even when the user "
                "names, picks or refers to a booking ('it', 'that booking'): until get_booking has "
                "been called this turn, the next tool is get_booking, never cancel_booking. If the "
                "user's current message names, picks or refers to a booking, call get_booking for "
                "it; otherwise call it without a booking ID, which returns the list of all "
                "bookings. Step 2: if get_booking returned the "
                "LIST, stop: do NOT call cancel_booking, the outcome is choose_booking. If it "
                "returned one booking that is cancelled or completed, stop: the outcome is "
                "booking_closed. If it returned not found, stop: not_found. If it returned one "
                "confirmed booking, call cancel_booking for that same booking ID. Never cancel a "
                "booking the user did not name in this cancellation request.",
        tools=["get_booking", "cancel_booking"],
        outcomes=["cancelled", "booking_closed", "not_found", "choose_booking", "failed"]),
    "add_baggage": Intent(
        desc="The user wants extra baggage or luggage on an existing booking. Examples: 'add 10 kg "
             "baggage to BK1001', 'I need more luggage', 'extra bag for my trip'. Also a reply "
             "that only gives a booking ID or the weight after the agent asked for it.",
        context="Step 1: the FIRST tool call is ALWAYS get_booking, exactly once, even when the user "
                "names, picks or refers to a booking ('it', 'that booking'): until get_booking has "
                "been called this turn, the next tool is get_booking, never add_baggage. If the "
                "user's current message names, picks or refers to a booking, call get_booking for "
                "it; otherwise call it without a booking ID, which returns the list of all "
                "bookings. Step 2: if get_booking "
                "returned the LIST, stop: the outcome is choose_booking. If it returned one booking "
                "that is cancelled or completed, stop: booking_closed. If not found, stop: "
                "not_found. If it returned one confirmed booking, call add_baggage for that same "
                "booking ID with the weight; the outcome is baggage_added, or baggage_error if the "
                "tool returned an error.",
        tools=["get_booking", "add_baggage"],
        outcomes=["baggage_added", "booking_closed", "not_found", "choose_booking", "baggage_error",
                  "failed"]),
    "select_seat": Intent(
        desc="The user wants to pick or change a seat on an existing booking. Examples: 'seat 14C "
             "on BK1002', 'I want seat 8A', 'choose my seat'. Also a reply that only gives a "
             "booking ID or a seat after the agent asked for it.",
        context="Step 1: the FIRST tool call is ALWAYS get_booking, exactly once, even when the user "
                "names, picks or refers to a booking ('it', 'that booking'): until get_booking has "
                "been called this turn, the next tool is get_booking, never select_seat. If the "
                "user's current message names, picks or refers to a booking, call get_booking for "
                "it; otherwise call it without a booking ID, which returns the list of all "
                "bookings. Step 2: if get_booking "
                "returned the LIST, stop: the outcome is choose_booking. If it returned one booking "
                "that is cancelled or completed, stop: booking_closed. If not found, stop: "
                "not_found. If it returned one confirmed booking, call select_seat for that same "
                "booking ID with the seat; the outcome is seat_selected, or seat_error if the tool "
                "returned an error.",
        tools=["get_booking", "select_seat"],
        outcomes=["seat_selected", "booking_closed", "not_found", "choose_booking", "seat_error", "failed"]),
    "greeting": Intent(
        desc="Greetings, thanks, goodbyes, small talk, or asking what the agent can do, with no "
             "flight request in it. Examples: 'hi', 'good morning', 'how are you', 'thanks', "
             "'bye', 'what can you do?', 'are you a bot?'. If the message also asks about flights "
             "or a booking, it is NOT a greeting.",
        context="The user is greeting or making small talk. No tool is needed. Pick the category: "
                "opening the conversation, closing it, or asking what the agent can do.",
        tools=[],
        outcomes=["greet", "closing", "capabilities"]),
    "out_of_scope": Intent(
        desc="Any request that is not searching or booking flights, checking, changing or cancelling "
             "a booking, extra baggage or seat selection. Examples: hotels, cabs, visas, meals, "
             "check-in, complaints, refund status, weather, general questions.",
        context="The request is outside the flight desk's services. No tool is needed.",
        tools=[],
        outcomes=["out_of_scope"]),
}

# ======================= OUTCOMES =======================
OUTCOMES = {
    "greet": Outcome(
        desc="Opening or friendly small talk: hello, good morning, how are you, ok, cool.",
        reply="Hi! I can search and book flights, and change, cancel or add baggage and seats to "
              "a booking. How can I help?"),
    "closing": Outcome(
        desc="Thanking or ending the conversation: thanks, bye, that's all, see you.",
        reply="You're welcome! Have a great trip, and come back anytime you need help with a flight."),
    "capabilities": Outcome(
        desc="Asking what the agent can do or who it is: what can you do, help, are you a bot.",
        reply="I'm a flight desk assistant. I can search and book flights, show your bookings, "
              "change a date, cancel, add extra baggage and pick a seat."),
    "out_of_scope": Outcome(
        desc="The request is outside the flight desk's services.",
        reply="Sorry, I can only help with flights: searching, booking, changing, cancelling, "
              "baggage and seats."),
    "flights_found": Outcome(
        desc="search_flights returned a list of flights (count is 1 or more).",
        reply="Flights from {origin} to {destination} on {date} for {passengers} passenger(s):\n"
              "{flights}\nTo book one, tell me the flight, the passenger name and economy or business."),
    "no_flights": Outcome(
        desc="search_flights returned no flights (count is 0).",
        reply="I found no flights from {origin} to {destination}. Try other cities."),
    "search_error": Outcome(
        desc="search_flights returned an error (a bad or past date, or the same city twice).",
        reply="I couldn't search flights: {error}."),
    "booked": Outcome(
        desc="book_flight returned a new booking with a booking_id.",
        reply="Booked! {booking_id}: {passenger_name}, {route} on {date}, {seat_class}, "
              "{fare_type} fare, total {price} INR."),
    "choose_flight": Outcome(
        desc="book_flight returned the error 'no flight was chosen': the user did not name or pick a flight.",
        reply="Which flight would you like to book? Please give the flight ID, for example FL102."),
    "flight_not_found": Outcome(
        desc="book_flight returned an error saying the flight was not found.",
        reply="I couldn't find that flight. Please check the flight ID."),
    "book_error": Outcome(
        desc="book_flight returned an error that is not 'no flight was chosen' or 'flight not found'.",
        reply="I couldn't complete the booking: {error}."),
    "booking_confirmed": Outcome(
        desc="get_booking returned ONE booking (with a booking_id) whose status is confirmed.",
        reply="Booking {booking_id} is confirmed: {passenger_name}, {route} on {date}, {seat_class} "
              "({fare_type} fare)."),
    "booking_cancelled": Outcome(
        desc="get_booking returned ONE booking (with a booking_id) whose status is cancelled.",
        reply="Booking {booking_id} ({passenger_name}, {route} on {date}) was cancelled."),
    "booking_completed": Outcome(
        desc="get_booking returned ONE booking (with a booking_id) whose status is completed.",
        reply="Booking {booking_id} ({passenger_name}, {route} on {date}) has already been flown."),
    "not_found": Outcome(
        desc="A tool returned an error saying the booking was not found.",
        reply="I couldn't find booking {booking_id}. Please check the ID."),
    "booking_list": Outcome(
        desc="get_booking returned the LIST of all bookings (a 'bookings' list, no single booking).",
        reply="Here are your bookings:\n{bookings}\nWhich booking ID would you like to check?"),
    "choose_booking": Outcome(
        desc="get_booking returned the LIST of all bookings (a 'bookings' list, no single booking), "
             "so the user must choose which booking they mean.",
        reply="Here are your bookings:\n{bookings}\nWhich booking ID do you mean?"),
    "booking_closed": Outcome(
        desc="get_booking returned ONE booking whose status is cancelled or completed, so it can't "
             "be changed.",
        reply="Booking {booking_id} ({route}) is {status}, so it can't be changed."),
    "changed": Outcome(
        desc="change_flight was called and returned the new date.",
        reply="Booking {booking_id} ({route}) is moved to {new_date}. Change fee: {fee} INR."),
    "change_error": Outcome(
        desc="change_flight returned an error.",
        reply="I couldn't change the booking: {error}."),
    "cancelled": Outcome(
        desc="cancel_booking was called and returned status cancelled.",
        reply="Booking {booking_id} ({route}) is cancelled (reason: {reason}). Refund: {refund} INR."),
    "baggage_added": Outcome(
        desc="add_baggage was called and returned the baggage total.",
        reply="Added {kg} kg of extra baggage to booking {booking_id} ({route}). Fee: {fee} INR."),
    "baggage_error": Outcome(
        desc="add_baggage returned an error.",
        reply="I couldn't add the baggage: {error}."),
    "seat_selected": Outcome(
        desc="select_seat was called and returned the seat.",
        reply="Seat {seat} is yours on booking {booking_id} ({route})."),
    "seat_error": Outcome(
        desc="select_seat returned an error.",
        reply="I couldn't assign that seat: {error}."),
    "failed": Outcome(
        desc="A tool returned an error that is not covered by another ending.",
        reply="Something went wrong on our side. I'm handing you over to a human."),
}

def main():
    """Initialize Jev and run the interactive agent."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    model = SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY"))
    # Initialize Cloudflare Clef instead of Jev:
    # model = CloudflareModel(
    #     api_token=os.environ["CLOUDFLARE_API_TOKEN"],
    #     account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
    #     model="clef",
    # )

    agent = Agent(
        tools=[search_flights, book_flight, get_booking, change_flight,
               cancel_booking, add_baggage, select_seat],
        intents=INTENTS, outcomes=OUTCOMES, model=model,
        memory=ConversationBufferMemory(k=7),
        # checkpointer=SqliteCheckpointer("flight_desk_agent.db"),
    )

    print('Flight desk: try bookings BK1001, BK1002, or completed booking BK1003.')
    print("Demo inventory resets on restart. Ctrl+C to quit.")
    while True:
        try:
            message = input("YOU> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if message:
            result = agent.turn(message)
            print("AGENT>", result.reply)


if __name__ == "__main__":
    main()
