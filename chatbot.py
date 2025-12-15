import re
from datetime import datetime
from models import db, User, Ticket, is_valid_email
import os
from dotenv import load_dotenv

load_dotenv()

_context = {}  # session_id -> {state, name, email, age, date}

_PATTERNS = [
    (r'\b(hello|hi|hey)\b', "👋 Hello! Welcome to MuseumHub. How can I assist you today?"),
    (r'\b(help|support|what can you do)\b', "📋 I can help you with:\n• Book Ticket\n• My Bookings\n• Cancel Ticket (by ID)\n• Pricing\n• Museum Timings\n• Policies\n• Guidelines"),
    (r'pricing|price|cost|charges', "💰 Ticket Pricing:\n• Regular Entry: Rs 500 per ticket\n• Children (below 12): Rs 300\n• Group Booking (10+): 10% discount\n• Students: Rs 400 with valid ID"),
    (r'timing|time|hours|open|working', "🕐 Museum Hours:\n• Opening: 9:00 AM\n• Closing: 6:00 PM\n• Last Entry: 5:00 PM\n• Closed on Mondays\n• Online Booking: 24/7"),
    (r'policies|policy|rules', (
        "📋 Museum Policies:\n"
        "1️⃣ Age Requirement: Minimum 18 years to book\n"
        "2️⃣ Cancellation: Within 48 hours of booking for refund\n"
        "3️⃣ Multiple Tickets: One booking per person per visit\n"
        "4️⃣ Refund Policy: Not allowed if you fail to visit\n"
        "5️⃣ ID Proof: Required at entrance for verification"
    )),
    (r'guidelines|guide|what should i know', (
        "📌 Important Guidelines:\n"
        "✓ Carry valid ID proof\n"
        "✓ Arrive 15 mins before entry time\n"
        "✓ Photography allowed in designated areas\n"
        "✓ No food/drinks in galleries\n"
        "✓ Respect historical artifacts"
    )),
    (r'services?|what do you offer', "🎫 Our Services:\n• Ticket Booking\n• Cancellation\n• View Your Bookings\n• PDF Ticket Generation with QR Code\n• Email Confirmation"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in _PATTERNS]
FALLBACK = "❓ I'm sorry, I don't understand that. Could you please clarify? Try: 'help' for available commands."

def _get_user_tickets(user_id):
    """Get all tickets for a user from PostgreSQL database."""
    try:
        tickets = Ticket.query.filter_by(user_id=user_id).all()
        if not tickets:
            return "📭 No bookings yet. Type 'book ticket' to create one!"
        
        ticket_list = "🗂 Your Bookings:\n"
        for ticket in tickets:
            ticket_list += f"🎟 ID: {ticket.id} | Name: {ticket.name} | Email: {ticket.email} | Age: {ticket.age}\n"
        return ticket_list
    except Exception as e:
        return f"Error fetching bookings: {str(e)}"

def _delete_user_ticket(user_id, ticket_id):
    """Delete a ticket if it belongs to the user."""
    try:
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return False, "Ticket not found."
        if ticket.user_id != user_id:
            return False, "❌ This ticket doesn't belong to you!"
        
        db.session.delete(ticket)
        db.session.commit()
        return True, f"✅ Ticket {ticket_id} cancelled successfully!"
    except Exception as e:
        db.session.rollback()
        return False, f"Error cancelling ticket: {str(e)}"

def _reset_flow(sid):
    """Reset the conversation flow for a session."""
    _context.pop(sid, None)

def _process_flow(sid, msg, user_id=None):
    """Process multi-step booking flow."""
    if sid not in _context:
        return None
    
    st = _context[sid]["state"]
    
    if st == "need_name":
        nm = msg.strip()
        if not nm or len(nm) < 2:
            return "❌ Please enter a valid name (at least 2 characters)."
        
        _context[sid]["name"] = nm
        _context[sid]["state"] = "need_email"
        return "📧 Enter your email address:"
    
    if st == "need_email":
        email = msg.strip()
        if not is_valid_email(email):
            return "❌ Please enter a valid email address."
        
        _context[sid]["email"] = email
        _context[sid]["state"] = "need_age"
        return "👤 Enter your age:"
    
    if st == "need_age":
        try:
            age = int(msg.strip())
            if age < 18:
                _reset_flow(sid)
                return "❌ Sorry, you must be 18 or older to book a ticket."
            if age > 120:
                return "❌ Please enter a valid age."
            
            _context[sid]["age"] = age
            _context[sid]["state"] = "confirm"
            return f"✅ Confirm booking:\nName: {_context[sid]['name']}\nEmail: {_context[sid]['email']}\nAge: {age}\n\nType 'yes' to confirm or 'no' to cancel:"
        except ValueError:
            return "❌ Please enter a valid age (number)."
    
    if st == "confirm":
        low = msg.lower()
        if low in ("yes", "y"):
            if not user_id:
                _reset_flow(sid)
                return "⚠️ Please login first to complete booking! Type 'book ticket' to get started."
            
            try:
                new_ticket = Ticket(
                    name=_context[sid]["name"],
                    email=_context[sid]["email"],
                    age=_context[sid]["age"],
                    user_id=user_id
                )
                db.session.add(new_ticket)
                db.session.commit()
                ticket_id = new_ticket.id
                _reset_flow(sid)
                return f"✅ Booking confirmed!\n🎟 Ticket ID: {ticket_id}\n📧 Confirmation sent to {_context[sid]['email']}\n\nPlease visit /my_tickets to view your booking and download PDF."
            except Exception as e:
                db.session.rollback()
                _reset_flow(sid)
                return f"❌ Error creating booking: {str(e)}"
        
        if low in ("no", "n"):
            _reset_flow(sid)
            return "❌ Booking cancelled. Type 'book ticket' to start again."
        
        return "❓ Please reply 'yes' or 'no'."
    
    return None

def get_chatbot_response(message: str, session_id: str, user_id: int = None) -> str:
    """Get chatbot response with database integration."""
    msg = message.strip()
    low = msg.lower()

    # Book Ticket - Start flow
    if re.search(r'\bbook\s+ticket\b', low):
        if not user_id:
            return "🔐 Please login first at /login to book a ticket!"
        _context[session_id] = {"state": "need_name"}
        return "📝 Let's book a ticket!\n\nWhat is your full name?"

    # Process ongoing flow
    flow_reply = _process_flow(session_id, msg, user_id)
    if flow_reply:
        return flow_reply

    # Cancel Ticket
    m = re.match(r'cancel\s+ticket\s+(\d+)', low)
    if m:
        if not user_id:
            return "🔐 Please login first to cancel a ticket!"
        success, msg_text = _delete_user_ticket(user_id, int(m.group(1)))
        return msg_text

    # My Bookings
    if low == "my bookings":
        if not user_id:
            return "🔐 Please login first to view your bookings!"
        return _get_user_tickets(user_id)

    # Pattern matching
    for rx, rep in _COMPILED:
        if rx.search(low):
            return rep

    return FALLBACK

