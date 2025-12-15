from flask import Flask, render_template, redirect, url_for, request, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
import stripe
from flask_cors import CORS
from models import db  # Import the db from model.py
from chatbot import get_chatbot_response
from uuid import uuid4
import os
import io
import qrcode
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import smtplib
from email.message import EmailMessage
import mimetypes
from dotenv import load_dotenv
import logging

# Load .env from project root if present — put SMTP settings here (see .env.example)
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://museum_user:krati123@localhost:5432/museum_chatbot"
)
app.config['STRIPE_PUBLIC_KEY'] = 'your_stripe_public_key'
app.config['STRIPE_SECRET_KEY'] = 'your_stripe_secret_key'

# Initialize the app with the db
db.init_app(app)

babel = Babel(app)
CORS(app)

stripe.api_key = app.config['STRIPE_SECRET_KEY']

def get_locale():
    return session.get('locale', 'en')

babel.init_app(app, locale_selector=get_locale)

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)


@app.route('/set_locale/<locale>')
def set_locale(locale):
    session['locale'] = locale
    return redirect(request.referrer)

@app.route('/test_locale')
def test_locale():
    return f"Current locale: {get_locale()}"

@app.route('/logout')
def logout():
    # Logic to log out the user, e.g., clearing the session
    session.clear()
    return redirect(url_for('login'))  # Redirect to the login page or homepage

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/view')
def view():
    return render_template('view.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Process form data
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        # Here you can handle the form data, e.g., send an email, save to a database, etc.
        
        return "Thank you for your message!"  # Or redirect to a 'thank you' page
    return render_template('contact.html')




@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        from models import User, is_valid_email
        
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation errors list
        errors = []
        
        # 1. Check if all fields are provided
        if not username:
            errors.append("Username cannot be empty.")
        if not email:
            errors.append("Email cannot be empty.")
        if not password:
            errors.append("Password cannot be empty.")
        if not confirm_password:
            errors.append("Please confirm your password.")
        
        # 2. Validate email format
        if email and not is_valid_email(email):
            errors.append("Please enter a valid email address (e.g., user@example.com).")
        
        # 3. Check if passwords match
        if password and confirm_password and password != confirm_password:
            errors.append("Passwords do not match.")
        
        # 4. Check password strength (minimum length)
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        
        # 5. Check if email is already registered
        if email and is_valid_email(email):
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                errors.append(f"A user with email '{email}' is already registered. Please use a different email or try logging in.")
        
        # 6. Check if username is already taken
        if username:
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                errors.append(f"Username '{username}' is already taken. Please choose a different username.")
        
        # If there are errors, return the form with error messages
        if errors:
            return render_template('register.html', errors=errors, username=username, email=email)
        
        # All validations passed, create user
        try:
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            return render_template('register.html', success=f"Registration successful! You can now log in with email '{email}'.")
        except Exception as e:
            db.session.rollback()
            errors.append(f"An error occurred during registration: {str(e)}")
            return render_template('register.html', errors=errors, username=username, email=email)
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from models import User, is_valid_email
        
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        errors = []
        
        # 1. Check if all fields are provided
        if not email:
            errors.append("Email cannot be empty.")
        if not password:
            errors.append("Password cannot be empty.")
        
        # 2. Validate email format
        if email and not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        
        # If there are validation errors, return with error messages
        if errors:
            return render_template('login.html', errors=errors, email=email)
        
        # 3. Try to find user by email
        try:
            user = User.query.filter_by(email=email, password=password).first()
            if user:
                session['user_id'] = user.id
                session['username'] = user.username
                return redirect(url_for('book_ticket'))
            else:
                # Generic error for security: don't reveal if email exists or password is wrong
                errors.append("Login failed. Email or password is incorrect. Please try again or register if you don't have an account.")
                return render_template('login.html', errors=errors, email=email)
        except Exception as e:
            errors.append(f"An error occurred during login: {str(e)}")
            return render_template('login.html', errors=errors, email=email)
    
    return render_template('login.html')

@app.route('/book_ticket', methods=['GET', 'POST'])
def book_ticket():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        from models import Ticket, User
        
        try:
            # Verify user exists in database
            user = User.query.get(session['user_id'])
            if not user:
                session.clear()
                return redirect(url_for('login'))
            
            # Validate age
            age = int(request.form.get('age', 0))
            if age < 18:
                return render_template('book_ticket.html', error="You must be 18 or older to book a ticket.")
            
            if age > 120:
                return render_template('book_ticket.html', error="Please enter a valid age.")
            
            # Get ticket details
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            
            if not name:
                return render_template('book_ticket.html', error="Name cannot be empty.")
            if not email:
                return render_template('book_ticket.html', error="Email cannot be empty.")
            
            # Create ticket
            ticket = Ticket(
                name=name,
                age=age,
                email=email,
                user_id=session['user_id']
            )
            db.session.add(ticket)
            db.session.commit()
            
            # generate PDF with QR and email it (best-effort)
            try:
                pdf_path = generate_ticket_pdf(ticket)
            except Exception as e:
                pdf_path = None
                app.logger.exception('Failed to generate PDF')

            # Try to email the PDF to the user. If mail settings are not configured, skip silently.
            try:
                if pdf_path:
                    send_email_with_attachment(
                        to_email=ticket.email,
                        subject=f"Your ticket #{ticket.id}",
                        body=f"Hello {ticket.name},\n\nAttached is your ticket (ID: {ticket.id}). Please present the attached PDF at the museum.",
                        attachment_path=pdf_path
                    )
            except Exception:
                app.logger.exception('Failed to send ticket email')

            return redirect(url_for('booking_success', ticket_id=ticket.id))
        
        except ValueError:
            return render_template('book_ticket.html', error="Please enter a valid age (number).")
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Error during ticket booking')
            return render_template('book_ticket.html', error=f"An error occurred while booking your ticket. Please try again.")
    
    return render_template('book_ticket.html')


def generate_ticket_pdf(ticket):
    """Create a PDF for the ticket and return the file path.

    Uses reportlab to draw text and embeds a QR code generated from a URL to the ticket.
    """
    tickets_dir = os.path.join(app.static_folder, 'tickets')
    os.makedirs(tickets_dir, exist_ok=True)
    pdf_filename = f"ticket_{ticket.id}.pdf"
    pdf_path = os.path.join(tickets_dir, pdf_filename)

    # Generate QR image into memory
    qr_payload = url_for('ticket_pdf', ticket_id=ticket.id, _external=True)
    qr = qrcode.make(qr_payload)
    qr_io = io.BytesIO()
    qr.save(qr_io, format='PNG')
    qr_io.seek(0)

    # Create PDF
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 80, f"Museum Ticket #{ticket.id}")

    # User info
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 120, f"Name: {ticket.name}")
    c.drawString(50, height - 140, f"Email: {ticket.email}")
    c.drawString(50, height - 160, f"Age: {ticket.age}")

    # QR image on the right
    img_reader = ImageReader(qr_io)
    img_size = 160
    c.drawImage(img_reader, width - img_size - 50, height - img_size - 120, width=img_size, height=img_size)

    # Footer / instructions
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, 80, "Please present this ticket (PDF with QR) at the museum entrance.")

    c.showPage()
    c.save()

    return pdf_path


def send_email_with_attachment(to_email, subject, body, attachment_path):
    """Send an email with attachment using SMTP settings from environment variables.

    Required environment variables:
    - SMTP_SERVER (e.g. smtp.gmail.com)
    - SMTP_PORT (e.g. 465 for SSL or 587 for STARTTLS)
    - SMTP_USERNAME
    - SMTP_PASSWORD
    - FROM_EMAIL (optional, defaults to SMTP_USERNAME)
    """
    # Read settings from environment or .env file
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '0'))
    smtp_user = os.getenv('SMTP_USERNAME')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    from_email = os.getenv('FROM_EMAIL') or smtp_user

    if not smtp_server or not smtp_port or not smtp_user or not smtp_pass:
        # Mail not configured
        app.logger.warning('SMTP not configured — skipping email')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg.set_content(body)

    # Attach file
    ctype, encoding = mimetypes.guess_type(attachment_path)
    if ctype is None:
        ctype = 'application/octet-stream'
    maintype, subtype = ctype.split('/', 1)
    with open(attachment_path, 'rb') as f:
        file_data = f.read()
    msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=os.path.basename(attachment_path))

    # Connect and send
    if smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    else:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
    server.login(smtp_user, smtp_pass)
    server.send_message(msg)
    server.quit()
    return True


@app.route('/booking_success/<int:ticket_id>')
def booking_success(ticket_id):
    return render_template('booking_success.html', ticket_id=ticket_id)


@app.route('/ticket_pdf/<int:ticket_id>')
def ticket_pdf(ticket_id):
    # Serve generated ticket PDF from static/tickets
    filename = f"ticket_{ticket_id}.pdf"
    tickets_dir = os.path.join(app.static_folder, 'tickets')
    return send_from_directory(tickets_dir, filename)

@app.route('/my_tickets')
def my_tickets():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from models import Ticket
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from models import Ticket
    try:
        # Verify the ticket belongs to the current user before deleting
        ticket = Ticket.query.get(ticket_id)
        if ticket and ticket.user_id == session['user_id']:
            db.session.delete(ticket)
            db.session.commit()
        else:
            app.logger.warning(f"Unauthorized delete attempt for ticket {ticket_id} by user {session['user_id']}")
    except Exception as e:
        db.session.rollback()
        app.logger.exception('Error deleting ticket')
    
    return redirect(url_for('my_tickets'))

@app.route('/payment/<int:ticket_id>', methods=['GET', 'POST'])
def payment(ticket_id):
    if request.method == 'POST':
        try:
            stripe.PaymentIntent.create(
                amount=1000,  # amount in cents
                currency='usd',
                payment_method=request.form['payment_method_id'],
                confirmation_method='manual',
                confirm=True
            )
            return "Payment successful!"
        except Exception as e:
            return f"An error occurred: {str(e)}", 400  # Better error handling
    return render_template('payment.html', stripe_public_key=app.config['STRIPE_PUBLIC_KEY'], ticket_id=ticket_id)


@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if 'chatbot_session_id' not in session:
        session['chatbot_session_id'] = str(uuid4())
    
    user_id = session.get('user_id')  # Get logged-in user ID if available
    
    if request.method == 'POST':
        data = request.get_json() or {}
        user_message = data.get('message', '')
        bot_response = get_chatbot_response(user_message, session['chatbot_session_id'], user_id)
        return jsonify({"response": bot_response})
    return render_template('chatbot.html')
    
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# @app.before_first_request
# def create_tables():
#     db.create_all()

if __name__ == '__main__':
    with app.app_context():
        # Log database configuration
        logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Create tables only if they don't exist (preserves all data)
        logger.info("Creating database tables...")
        try:
            db.create_all()
            logger.info("Database tables ready!")
            
            # Log existing users and tickets count
            from models import User, Ticket
            total_users = User.query.count()
            total_tickets = Ticket.query.count()
            logger.info(f"Database Status: {total_users} users, {total_tickets} tickets")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            logger.info("Attempting database repair...")
            try:
                db.session.rollback()
                db.create_all()
                logger.info("Database repair completed!")
            except Exception as e2:
                logger.critical(f"Database repair failed: {str(e2)}")
    
    logger.info("Starting Flask application...")
    app.run(debug=True)
