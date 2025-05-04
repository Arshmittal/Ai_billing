from venv import logger
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from authlib.integrations.flask_client import OAuth
import requests
import json
import os
import hashlib
from datetime import datetime
import logging
from dotenv import load_dotenv
import logging
import PyPDF2
from functools import wraps
from docx import Document
from pymongo import MongoClient
from datetime import datetime,timedelta
from bson import ObjectId
from bs4 import BeautifulSoup
from flask_cors import CORS

from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

 

# Configuration
API_URL = os.getenv('API_URL')
API_KEY = os.getenv('API_KEY')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
SECRET_KEY = os.getenv('SECRET_KEY')
MONGO_URI = os.getenv('MONGO_URI')
URL = 'https://www.revisor.mn.gov/statutes/cite/245D/full'
MODE = os.getenv('MODE', 'production')


dummy_user = {
    "name": "Tester",
    "email": "tester@example.com",
    "picture": "/static/default-profile.png",
    "last_login": datetime.utcnow()
}


app = Flask(__name__, static_folder='public/static')
CORS(app) 
app.secret_key = SECRET_KEY 
app.config['SESSION_COOKIE_NAME'] = 'google-login-session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)  # Increased session lifetime
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS

app.logger.setLevel(logging.INFO)


app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# MongoDB Setup
client = MongoClient(os.getenv("MONGO_URI"))  # Use the MongoDB URI from the .env file
db = client["test"]  # Replace with your database name
users_collection = db["users"]
chats_collection = db["chats"]
# Add this to your MongoDB setup section
dashboard_stats_collection = db["dashboard_stats"]
hashes_collection = db["hashes_new"]



oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',  # Simplified scope
        'prompt': 'select_account'
    }
)


# Routes
@app.route('/', methods=['GET'])
def root():
    """
    Render the homepage with the user interface.
    """
    user = session.get('user')
    if user:
        # Check if user has dashboard stats, initialize if not
        stats = dashboard_stats_collection.find_one({"user_email": user.get('email')})
        if not stats:
            initialize_new_user_dashboard_stats(user.get('email'))
    
    return render_template('DashBoard.html', user=user)

@app.route('/home', methods=['GET'])
def home():
    """
    Redirect to the root.
    """
    return redirect(url_for('root'))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

app.json_encoder = JSONEncoder

@app.route('/login')
def login():
    session.clear()
    session['oauth_state'] = os.urandom(16).hex()
    session.modified = True
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(
        redirect_uri=redirect_uri,
        state=session['oauth_state']
    )

@app.route('/google/callback')
def google_callback():
    try:
        state = request.args.get('state')
        stored_state = session.get('oauth_state')

        if not state or not stored_state or state != stored_state:
            raise ValueError("State verification failed")
        
        session.pop('oauth_state', None)

        token = google.authorize_access_token()
        if not token:
            raise ValueError("Failed to get access token")

        # Get user info from Google
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo', token=token)
        user_info = resp.json()
        
        if not user_info or 'email' not in user_info:
            raise ValueError("Failed to get user info")

        # Store user data and OAuth token in MongoDB
        user_data = {
            "name": user_info.get("name", "User"),
            "email": user_info["email"],
            "picture": user_info.get("picture", "/static/user.png"),
            "last_login": datetime.utcnow(),
            "oauth_token": token  # Store OAuth token for future API requests
        }

        try:
            result = users_collection.update_one(
                {"email": user_data["email"]},
                {"$set": user_data},
                upsert=True
            )
            logger.info(f"User data updated: matched={result.matched_count}, modified={result.modified_count}, upserted_id={result.upserted_id}")
        except Exception as e:
            logger.error(f"Error saving user data to MongoDB: {e}")

        session.permanent = True
        session['user'] = user_data

        return redirect(url_for('home'))

    except Exception as e:
        logger.error(f"Error in Google callback: {str(e)}")
        session.clear()
        return render_template('error.html', error="Authentication failed. Please try again.")


    




@app.route('/login_page', methods=['GET'])
def login_page():
   return redirect(url_for('login'))




@app.route('/check-login-status', methods=['GET'])
def check_login_status():
    user = session.get('user')  # Retrieve the user from the session
    if user:  # Check if the user exists in the session
        return jsonify({'loggedIn': True})  # User is logged in
    return jsonify({'loggedIn': False})  # User is not logged in


@app.route('/get-user-info', methods=['GET'])
def get_user_info():
    """
    Return the current user's information as JSON.
    """
    user = session.get('user')
    if user:
        return jsonify(user)
    return jsonify({}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    """Return dashboard statistics based on login status"""
    user = session.get('user')
    
    if user:
        # User is logged in, get their specific data
        user_email = user.get('email')
        stats = dashboard_stats_collection.find_one({"user_email": user_email})
        
        if not stats:
            # Initialize stats for this user with zeros
            initialize_new_user_dashboard_stats(user_email)
            stats = dashboard_stats_collection.find_one({"user_email": user_email})
        
        # Convert ObjectId to string for JSON serialization
        stats['_id'] = str(stats['_id'])
        return jsonify(stats)
    else:
        # User is not logged in, return aggregate data from all users
        return get_aggregate_dashboard_stats()

def initialize_new_user_dashboard_stats(user_email):
    """Create new user dashboard statistics starting with zeros"""
    dashboard_stats_collection.update_one(
        {"user_email": user_email},
        {"$set": {
            "user_email": user_email,
            "total_revenue": 0,
            "revenue_change": 0,
            "total_claims": 0,
            "claims_change": 0,
            "active_clients": 0,
            "clients_change": 0,
            "staff_members": 0,
            "staff_change": 0,
            "denied_claims": 0,
            "voided_claims": 0,
            "replaced_claims": 0,
            "payroll": 0,
            "payroll_total": 0,
            "revenue_by_payer": {
                "Medicare": {
                    "this_month": 0,
                    "last_3_months": 0,
                    "last_6_months": 0,
                    "last_12_months": 0,
                    "lifetime": 0
                },
                "Medicaid": {
                    "this_month": 0,
                    "last_3_months": 0,
                    "last_6_months": 0,
                    "last_12_months": 0,
                    "lifetime": 0
                },
                "Blue Cross": {
                    "this_month": 0,
                    "last_3_months": 0,
                    "last_6_months": 0,
                    "last_12_months": 0,
                    "lifetime": 0
                }
            },
            "last_updated": datetime.utcnow()
        }},
        upsert=True
    )

def get_aggregate_dashboard_stats():
    """Get aggregate statistics from all users"""
    # Use MongoDB aggregation to get totals
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_revenue": {"$sum": "$total_revenue"},
                "total_claims": {"$sum": "$total_claims"},
                "active_clients": {"$sum": "$active_clients"},
                "staff_members": {"$sum": "$staff_members"},
                "denied_claims": {"$sum": "$denied_claims"},
                "voided_claims": {"$sum": "$voided_claims"},
                "replaced_claims": {"$sum": "$replaced_claims"},
                "payroll_total": {"$sum": "$payroll_total"},
                "user_count": {"$sum": 1}
            }
        }
    ]
    
    result = list(dashboard_stats_collection.aggregate(pipeline))
    
    if result and len(result) > 0:
        agg_stats = result[0]
        
        # Calculate average changes (simplified approach)
        avg_changes_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "avg_revenue_change": {"$avg": "$revenue_change"},
                    "avg_claims_change": {"$avg": "$claims_change"},
                    "avg_clients_change": {"$avg": "$clients_change"},
                    "avg_staff_change": {"$avg": "$staff_change"}
                }
            }
        ]
        
        avg_changes = list(dashboard_stats_collection.aggregate(avg_changes_pipeline))
        changes = avg_changes[0] if avg_changes else {
            "avg_revenue_change": 0,
            "avg_claims_change": 0,
            "avg_clients_change": 0,
            "avg_staff_change": 0
        }
        
        # Aggregate revenue by payer data
        # This is more complex, but let's create a simplified version
        revenue_by_payer = {
            "Medicare": {"this_month": 0, "last_3_months": 0, "last_6_months": 0, "last_12_months": 0, "lifetime": 0},
            "Medicaid": {"this_month": 0, "last_3_months": 0, "last_6_months": 0, "last_12_months": 0, "lifetime": 0},
            "Blue Cross": {"this_month": 0, "last_3_months": 0, "last_6_months": 0, "last_12_months": 0, "lifetime": 0}
        }
        
        # Collect all user data to calculate payer totals
        all_users = dashboard_stats_collection.find({})
        for user_data in all_users:
            if "revenue_by_payer" in user_data:
                for payer, periods in user_data["revenue_by_payer"].items():
                    for period, amount in periods.items():
                        revenue_by_payer[payer][period] += amount
        
        return jsonify({
            "total_revenue": agg_stats.get("total_revenue", 0),
            "revenue_change": round(changes.get("avg_revenue_change", 0), 1),
            "total_claims": agg_stats.get("total_claims", 0),
            "claims_change": round(changes.get("avg_claims_change", 0), 1),
            "active_clients": agg_stats.get("active_clients", 0),
            "clients_change": round(changes.get("avg_clients_change", 0), 1),
            "staff_members": agg_stats.get("staff_members", 0),
            "staff_change": round(changes.get("avg_staff_change", 0), 1),
            "denied_claims": agg_stats.get("denied_claims", 0),
            "voided_claims": agg_stats.get("voided_claims", 0),
            "replaced_claims": agg_stats.get("replaced_claims", 0),
            "payroll": 0,  # Assuming this is a calculated field
            "payroll_total": agg_stats.get("payroll_total", 0),
            "revenue_by_payer": revenue_by_payer,
            "user_count": agg_stats.get("user_count", 0)
        })
    else:
        # Fallback to sample data if no users exist yet
        return jsonify({
            "total_revenue": 1236742,
            "revenue_change": 5.8,
            "total_claims": 1425,
            "claims_change": 3.2,
            "active_clients": 356,
            "clients_change": 1.9,
            "staff_members": 168,
            "staff_change": 0.5,
            "denied_claims": 87,
            "voided_claims": 12,
            "replaced_claims": 34,
            "payroll": 0,
            "payroll_total": 1236742.58,
            "revenue_by_payer": {
                "Medicare": {
                    "this_month": 256832.00,
                    "last_3_months": 768493.00,
                    "last_6_months": 1524986.00,
                    "last_12_months": 3042967.00,
                    "lifetime": 7564890.00
                },
                "Medicaid": {
                    "this_month": 168453.00,
                    "last_3_months": 489786.00,
                    "last_6_months": 983941.00,
                    "last_12_months": 1965832.00,
                    "lifetime": 4891453.00
                },
                "Blue Cross": {
                    "this_month": 126534.00,
                    "last_3_months": 359876.00,
                    "last_6_months": 722765.00,
                    "last_12_months": 1426543.00,
                    "lifetime": 3587654.00
                }
            },
            "user_count": 0
        })
    

@app.route('/dashboard')
def dashboard():
    """
    Redirect to the root.
    """
    user = session.get('user')
    return render_template('schedule.html', user=user)

@app.route('/create-doc')
def create_doc():
    """
    Redirect to the root.
    """
    user = session.get('user')
    return render_template('createdocument.html', user=user)


@app.route('/timesheet')
def timesheet():
    """
    Redirect to the root.
    """
    user = session.get('user')
    return render_template('timesheet.html', user=user)

@app.route('/billing_dashboard')
def billing_dashboard():
    """
    Redirect to the root.
    """
    user = session.get('user')
    return render_template('DashBoard.html', user=user)



app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx'}




@app.route('/schedule', methods=['GET'])
@login_required
def schedule():
    """
    Render the scheduling page.

    """
    user = session.get('user')
    user_email = user.get('email')
    
    # Check if the user has accepted the Terms of Service
    tos_collection = db["tos_accepted"]
    user_tos_status = tos_collection.find_one({"email": user_email})

    if not user_tos_status or not user_tos_status.get("accepted", False):
        # Redirect user to ToS page if not accepted
        return redirect(url_for('terms_of_service'))
    
    user = session.get('user')
    return render_template('schedule.html', user=user)
    






# Route to handle file deletion
@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'message': f'{filename} deleted successfully'})
    else:
        return jsonify({'error': f'{filename} not found'}), 404

@app.route('/static/<path:filename>')
def serve_static(filename):
    """
    Serve static files.
    """
    return send_from_directory(app.static_folder, filename)


from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_google_calendar_service(user_email):
    """Retrieve OAuth token from MongoDB and create a Google Calendar API service."""
    user = users_collection.find_one({"email": user_email})
    if not user or "oauth_token" not in user:
        raise ValueError("User not authenticated with Google")

    token_data = user["oauth_token"]

    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )

    return build('calendar', 'v3', credentials=creds)




from bson import ObjectId
shifts_collection = db["shifts"]

@app.route('/add-shift', methods=['POST'])
def add_shift():
    """Create a Google Calendar event using the user's stored OAuth token and save in MongoDB."""
    try:
        user_email = session.get('user', {}).get('email')
        if not user_email:
            return jsonify({"error": "User not logged in"}), 401

        # Get Google Calendar API service
        service = get_google_calendar_service(user_email)

        # Extract form data
        data = request.json
        title = data.get('title', 'New Shift')
        start_time = data.get('start')
        end_time = data.get('end')
        description = data.get('description', '')
        recipient_email = data.get('recipientEmail')

        # 245D Compliance Fields
        staff_name = data.get('staffName')
        staff_email = data.get('staffEmail')
        service_type = data.get('serviceType')
        clock_in = data.get('clockIn')
        clock_out = data.get('clockOut')
        internal_notes = data.get('internalNotes')

        event = {
            'summary': title,
            'description': description,
            'start': {'dateTime': start_time, 'timeZone': 'UTC'},
            'end': {'dateTime': end_time, 'timeZone': 'UTC'},
            'attendees': [{'email': recipient_email}],
        }

        # Insert event into Google Calendar
        event_result = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
        event_link = event_result.get('htmlLink')

        # Store in MongoDB with 245D Compliance Data
        shift_id = shifts_collection.insert_one({
            "title": title,
            "start": start_time,
            "end": end_time,
            "description": description,
            "recipient_email": recipient_email,
            "user_email": user_email,
            "event_link": event_link,

            # 245D Compliance Fields
            "staff_name": staff_name,
            "staff_email": staff_email,
            "service_type": service_type,
            "clock_in": clock_in,
            "clock_out": clock_out,
            "internal_notes": internal_notes
        }).inserted_id

        return jsonify({"message": "Shift created and invite sent!", "eventLink": event_link, "shift_id": str(shift_id)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-shifts', methods=['GET'])
@login_required
def get_shifts():
    """
    Fetch shifts for the logged-in user based on the provided date range.
    """
    start = request.args.get('start')
    end = request.args.get('end')
    user_email = session.get('user', {}).get('email')

    if not user_email:
        return jsonify({"error": "User not logged in."}), 401

    # Query the database for shifts within the specified date range
    shifts = shifts_collection.find({
        "user_email": user_email,
        "start": {"$gte": start},
        "end": {"$lte": end}
    })

    # Format the shifts for the calendar, including 245D Compliance Data
    formatted_shifts = []
    for shift in shifts:
        formatted_shifts.append({
            "id": str(shift["_id"]),  # Include the shift ID
            "title": shift["title"],
            "start": shift["start"],
            "end": shift["end"],
            "description": shift.get("description", ""),
            "eventLink": shift.get("event_link", "#"),  # Link to Google Calendar event
            
            # 245D Compliance Data
            "staffName": shift.get("staff_name", "N/A"),
            "staffEmail": shift.get("staff_email", "N/A"),
            "serviceType": shift.get("service_type", "N/A"),
            "clockIn": shift.get("clock_in", "N/A"),
            "clockOut": shift.get("clock_out", "N/A"),
            "internalNotes": shift.get("internal_notes", "N/A"),
        })

    return jsonify(formatted_shifts), 200


@app.route('/delete-shift/<shift_id>', methods=['DELETE'])
@login_required
def delete_shift(shift_id):
    """
    Delete a shift from the database.
    """
    shifts_collection.delete_one({"_id": ObjectId(shift_id)})
    return jsonify({"message": "Shift deleted successfully"}), 200





  
invoices_collection = db["invoices"]
@app.route('/create-invoice', methods=['POST'])
@login_required
def create_invoice():
    data = request.json
    invoice = {
        "client_name": data.get('client_name'),
        "service_type": data.get('service_type'),
        "service_date": data.get('service_date'),
        "service_location": data.get('service_location'),
        "items": data.get('items'),
        "sub_total": data.get('sub_total'),
        "discount": data.get('discount'),
        "total": data.get('total'),
        "status": "Pending"
    }
    invoices_collection.insert_one(invoice)
    return jsonify({"message": "Invoice created successfully"})

@app.route('/get-invoices', methods=['GET'])
@login_required
def get_invoices():
    invoices = invoices_collection.find()
    formatted_invoices = []
    for invoice in invoices:
        formatted_invoices.append({
            "client_name": invoice["client_name"],
            "service_type": invoice["service_type"],
            "service_date": invoice["service_date"],
            "service_location": invoice["service_location"],
            "items": invoice["items"],
            "sub_total": invoice["sub_total"],
            "discount": invoice["discount"],
            "total": invoice["total"],
            "status": invoice["status"]
        })
    return jsonify(formatted_invoices)

@app.route('/billing', methods=['GET'])
def billing():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('billing.html', user=user)

@app.route('/create-shift-front', methods=['GET'])
def create_shift_front():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('create-shift.html', user=user)

@app.route('/add-client', methods=['GET'])
def add_client():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('add-client.html', user=user)

@app.route('/view-client', methods=['GET'])
def view_client():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('view-client.html', user=user)


@app.route('/generate-invoice', methods=['GET'])
def generate_invoice():
    """
    Render the Generate Invoice page.
    """
    user = session.get('user')
    return render_template('generateinvoice.html', user=user)


@app.route('/view-invoice', methods=['GET'])
def view_invoice():
    """
    Render the View Invoice page.
    """
    user = session.get('user')
    return render_template('viewinvoice.html', user=user)

@app.route('/generateClaims', methods=['GET'])
def generateClaims():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('generateClaims.html', user=user)


@app.route('/add-employee', methods=['GET'])
def add_employee():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('add-employee.html', user=user)

from flask import Flask, render_template, request, send_file, jsonify
import pdfkit
import io
import os
import base64
from datetime import datetime

@app.route('/preview_pdf', methods=['POST'])
def preview_pdf():
    # Get form data
    client_name = request.form.get('client_name', '')
    document_type = request.form.get('document_type', '')
    program_name = request.form.get('program_name', '')
    print_name_title = request.form.get('print_name_title', '')
    date_review = request.form.get('date_review', '')
    date_revision = request.form.get('date_revision', '')
    signature = request.form.get('signature', '')
    
    # Remove header from base64 encoded signature if present
    if signature and ',' in signature:
        signature = signature.split(',')[1]
    
    # Create HTML content for preview
    html_content = render_template(
        'pdf_template.html',
        client_name=client_name,
        document_type=document_type,
        program_name=program_name,
        print_name_title=print_name_title,
        date_review=date_review,
        date_revision=date_revision,
        signature=signature
    )
    
    return html_content

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    # Get form data
    client_name = request.form.get('client_name', '')
    document_type = request.form.get('document_type', '')
    program_name = request.form.get('program_name', '')
    print_name_title = request.form.get('print_name_title', '')
    date_review = request.form.get('date_review', '')
    date_revision = request.form.get('date_revision', '')
    signature = request.form.get('signature', '')
    
    # Remove header from base64 encoded signature if present
    if signature and ',' in signature:
        signature = signature.split(',')[1]
    
    # Create HTML content for PDF
    html_content = render_template(
        'pdf_template.html',
        client_name=client_name,
        document_type=document_type,
        program_name=program_name,
        print_name_title=print_name_title,
        date_review=date_review,
        date_revision=date_revision,
        signature=signature
    )
    
    # Configure pdfkit options
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': 'UTF-8',
    }
    
    # Convert HTML to PDF
    try:
        # Note: For Windows, you may need to specify the path to wkhtmltopdf
        # config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')
        # pdf = pdfkit.from_string(html_content, False, options=options, configuration=config)
        
        pdf = pdfkit.from_string(html_content, False, options=options)
        
        # Create a BytesIO object
        pdf_io = io.BytesIO(pdf)
        pdf_io.seek(0)
        
        # Gen+erate a filename based on client name and document type
        filename = f"{client_name.split()[0]}_{document_type.split()[0]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        
        return send_file(
            pdf_io,
            mimetype='application/pdf',
            download_name=filename,
            as_attachment=True
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

from flask import Flask, request, jsonify, send_file

import os
import json
import uuid
import tempfile
from datetime import datetime
import PyPDF2
import io
import re
import fitz
from werkzeug.utils import secure_filename
from fpdf import FPDF
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

service_auth = db['service_auth']

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# In-memory database for demo purposes
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.0,  # Set to 0 for more deterministic responses
)


# Function to extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text


# Function to parse service auth data using GPT-3.5
def parse_service_auth_data_with_llm(text):
    prompt_template = PromptTemplate(
        input_variables=["text"],
        template="""
        Extract the following information from the healthcare service authorization text. 
        If the information is not present, respond with "Not found" for that field.
        
        Payer: (Look for insurance company name or MINNESOTA DEPT OF HUMAN SERVICES)
        Member ID: (Look for a member ID number, usually following 'Member ID' or similar)
        Service Auth #: (Look for a service authorization number, usually following 'Service Auth #' or similar)
        Procedure Service Code: (Look for a code like S5XXX where X are digits)
        Modifier Code: (Look for UA or UC, usually following the procedure code)
        Service Dates: (Look for a date range in format MM/DD/YYYY to MM/DD/YYYY)
        Units: (Look for a number following 'Units' or similar)
        Service Rate: (Look for a dollar amount following 'Service Rate' or similar)
        
        Here is the text from the service authorization document:
        {text}
        
        Format your response exactly like this, with only the extracted values:
        Payer: [payer]
        Member ID: [member_id]
        Service Auth #: [service_auth_num]
        Procedure Service Code: [procedure_code]
        Modifier Code: [modifier_code]
        Service Dates: [dates]
        Units: [units]
        Service Rate: [service_rate]
        """
    )
    
    chain = LLMChain(llm=llm, prompt=prompt_template)
    
    try:
        # Get the LLM output
        output = chain.invoke({"text": text})
        result = output['text']
        
        # Parse the structured output
        payer_match = re.search(r'Payer:\s*(.*?)(?:\n|$)', result)
        member_id_match = re.search(r'Member ID:\s*(.*?)(?:\n|$)', result)
        auth_match = re.search(r'Service Auth #:\s*(.*?)(?:\n|$)', result)
        procedure_code_match = re.search(r'Procedure Service Code:\s*(.*?)(?:\n|$)', result)
        modifier_code_match = re.search(r'Modifier Code:\s*(.*?)(?:\n|$)', result)
        dates_match = re.search(r'Service Dates:\s*(.*?)(?:\n|$)', result)
        units_match = re.search(r'Units:\s*(.*?)(?:\n|$)', result)
        service_rate_match = re.search(r'Service Rate:\s*(.*?)(?:\n|$)', result)
        
        # Extract and clean data from matches
        payer = payer_match.group(1).strip() if payer_match else ""
        payer = "" if payer.lower() == "not found" else payer
        
        member_id = member_id_match.group(1).strip() if member_id_match else ""
        member_id = "" if member_id.lower() == "not found" else member_id
        
        service_auth_num = auth_match.group(1).strip() if auth_match else ""
        service_auth_num = "" if service_auth_num.lower() == "not found" else service_auth_num
        
        procedure_code = procedure_code_match.group(1).strip() if procedure_code_match else ""
        procedure_code = "" if procedure_code.lower() == "not found" else procedure_code
        
        modifier_code = modifier_code_match.group(1).strip() if modifier_code_match else ""
        modifier_code = "" if modifier_code.lower() == "not found" else modifier_code
        
        dates = dates_match.group(1).strip() if dates_match else ""
        dates = "" if dates.lower() == "not found" else dates
        
        units = units_match.group(1).strip() if units_match else ""
        units = "" if units.lower() == "not found" else units
        
        service_rate = service_rate_match.group(1).strip() if service_rate_match else ""
        service_rate = "" if service_rate.lower() == "not found" else service_rate
        
        # Try to convert units to float for calculation
        try:
            units_float = float(units) if units else 0
        except ValueError:
            units_float = 0
        
        # Create services list with extracted data
        services = [{
            "id": str(uuid.uuid4()),
            "payer": payer,
            "memberId": member_id,
            "serviceAuthNumber": service_auth_num,
            "procedureServiceCode": procedure_code,
            "modifierCode": modifier_code,
            "dates": dates,
            "units": units,
            "serviceRate": service_rate,
            "usedUnits": "0",
            "totalHoursRemaining": f"{units_float} hrs",
            "hoursPerDay": "3",  # Default value
            "hoursPerWeek": "21",  # Default value
        }]
        
        return {"services": services}
    
    except Exception as e:
        print(f"Error parsing with OpenAI: {e}")
        # Fallback to regex-based parser if LLM parsing fails
        return parse_service_auth_data(text)


# Existing regex-based parser as fallback
def parse_service_auth_data(text):
    # Extract Member ID
    member_id_match = re.search(r'Member ID[:\s]+(\d+)', text)
    member_id = member_id_match.group(1) if member_id_match else ""
    
    # Extract Payer information
    payer_match = re.search(r'(MINNESOTA DEPT OF HUMAN SERVICES)', text, re.IGNORECASE)
    payer = payer_match.group(1) if payer_match else ""
    
    # Extract Service Auth Number
    auth_match = re.search(r'Service Auth #[:\s]+(\d+)', text)
    service_auth_num = auth_match.group(1) if auth_match else ""
    
    # Extract Procedure Service Code
    proc_code_match = re.search(r'S5\d+', text)
    procedure_code = proc_code_match.group(0) if proc_code_match else ""
    
    # Extract Modifier Code (if any)
    modifier_match = re.search(r'(?:' + re.escape(procedure_code) + r')?[,\s]+(UA|UC)?', text)
    modifier_code = modifier_match.group(1) if modifier_match and modifier_match.group(1) else ""
    
    # Extract Service Rate
    rate_match = re.search(r'Service Rate[:\s]+([\d.]+)', text)
    service_rate = rate_match.group(1) if rate_match else ""
    
    # Extract Units
    units_match = re.search(r'Units[:\s]+([\d.]+)', text)
    units = units_match.group(1) if units_match else ""
    
    # Extract Dates
    dates_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+[Tt]o\s+(\d{2}/\d{2}/\d{4})', text)
    dates = f"{dates_match.group(1)} To {dates_match.group(2)}" if dates_match else ""
    
    # Create services list with extracted data
    services = [{
        "id": str(uuid.uuid4()),
        "payer": payer,
        "memberId": member_id,
        "serviceAuthNumber": service_auth_num,
        "procedureServiceCode": procedure_code,
        "modifierCode": modifier_code,
        "dates": dates,
        "units": units,
        "serviceRate": service_rate,
        "usedUnits": "0",
        "totalHoursRemaining": f"{float(units) if units else 0} hrs",
        "hoursPerDay": "3",
        "hoursPerWeek": "21",
    }]
    
    return {"services": services}


@app.route('/api/extract-pdf', methods=['POST'])
def extract_pdf():
    try:
        # Check if the post request has the file part
        if 'pdf' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['pdf']
        
        # If user does not select file, browser also submit an empty part without filename
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Extract text from PDF
            text = extract_text_from_pdf(file_path)
            
            # Parse the text to extract service auth data
            parsed_data = parse_service_auth_data_with_llm(text)
            
            # Save to MongoDB
            if parsed_data and "services" in parsed_data and len(parsed_data["services"]) > 0:
                service_auth.insert_one(parsed_data["services"][0])
            
            # Clean up the file
            os.remove(file_path)
            
            return jsonify(parsed_data)
    
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return jsonify({"error": "Failed to process PDF"}), 500


@app.route('/api/manual-entry', methods=['POST'])
def manual_entry():
    try:
        data = request.json
        
        # Calculate hours per week
        daily_usage = float(data.get("dailyUsage", 0))
        hours_per_week = daily_usage * 7
        
        # Create a service auth record
        service = {
            "id": str(uuid.uuid4()),
            "payer": data.get("payer", ""),
            "memberId": data.get("memberId", ""),
            "serviceAuthNumber": data.get("serviceAuthNumber", ""),
            "procedureServiceCode": data.get("procedureServiceCode", ""),
            "modifierCode": data.get("modifierCode", ""),
            "dates": data.get("dates", ""),
            "units": data.get("units", ""),
            "serviceRate": data.get("serviceRate", ""),
            "usedUnits": "0",
            "totalHoursRemaining": f"{float(data.get('units', 0))} hrs",
            "hoursPerDay": data.get("dailyUsage", ""),
            "hoursPerWeek": str(hours_per_week),
        }
        
        # Add to our database
        service_auth.insert_one(service)
        
        return jsonify({"services": [service]})
    
    except Exception as e:
        print(f"Error processing manual entry: {e}")
        return jsonify({"error": "Failed to process manual entry"}), 500


@app.route('/api/export-pdf', methods=['POST'])
def export_pdf():
    try:
        # Create a PDF document
        pdf = FPDF()
        pdf.add_page()
        
        # Set font
        pdf.set_font("Arial", size=12)
        
        # Add title
        pdf.cell(200, 10, txt="Service Authorization Report", ln=True, align='C')
        
        # Add date
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.cell(200, 10, txt=f"Generated on: {current_date}", ln=True, align='L')
        
        # Get services data from MongoDB
        services = list(service_auth.find())
        
        # Add table headers
        pdf.set_font("Arial", style='B', size=10)
        pdf.cell(30, 10, txt="Member ID", border=1)
        pdf.cell(30, 10, txt="Service Auth #", border=1)
        pdf.cell(40, 10, txt="Procedure Code", border=1)
        pdf.cell(30, 10, txt="Units", border=1)
        pdf.cell(30, 10, txt="Service Rate", border=1)
        pdf.cell(30, 10, txt="Hours Per Day", border=1)
        pdf.ln()
        
        # Add data rows
        pdf.set_font("Arial", size=10)
        for service in services:
            pdf.cell(30, 10, txt=service.get("memberId", ""), border=1)
            pdf.cell(30, 10, txt=service.get("serviceAuthNumber", ""), border=1)
            pdf.cell(40, 10, txt=f"{service.get('procedureServiceCode', '')} {service.get('modifierCode', '')}", border=1)
            pdf.cell(30, 10, txt=service.get("units", ""), border=1)
            pdf.cell(30, 10, txt=service.get("serviceRate", ""), border=1)
            pdf.cell(30, 10, txt=service.get("hoursPerDay", ""), border=1)
            pdf.ln()
        
        # Save PDF to a buffer
        pdf_buffer = io.BytesIO()
        pdf.output(pdf_buffer)
        pdf_buffer.seek(0)
        
        # Send file as attachment
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='service_authorization.pdf'
        )
    
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({"error": "Failed to generate PDF"}), 500
    
@app.route('/serviceAuth', methods=['GET'])
def serviceAuth():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('service_auth.html', user=user)


client_details = db["client_details"]

# Configure upload folder for client photos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/save-client', methods=['POST'])
def save_client():
    try:
        # Get data from request
        client_data = request.json
        
        # Add creation timestamp
        client_data['createdAt'] = datetime.utcnow()
        
        # Insert data into MongoDB
        result = client_details.insert_one(client_data)
        
        # Return success response with the created client ID
        return jsonify({
            'success': True,
            'message': 'Client data saved successfully',
            'clientId': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        # Return error response
        return jsonify({
            'success': False,
            'message': f'Error saving client data: {str(e)}'
        }), 500


@app.route('/api/upload-photo/<client_id>', methods=['POST'])
def upload_photo(client_id):
    try:
        # Check if a client with this ID exists
        client = client_details.find_one({'_id': ObjectId(client_id)})
        if not client:
            return jsonify({
                'success': False,
                'message': 'Client not found'
            }), 404

        # Check if the post request has the file part
        if 'photo' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file part in the request'
            }), 400
            
        file = request.files['photo']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No selected file'
            }), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add client ID to filename to ensure uniqueness
            new_filename = f"{client_id}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            file.save(file_path)
            
            # Update client record with photo path
            client_details.update_one(
                {'_id': ObjectId(client_id)},
                {'$set': {'photoUrl': f'/uploads/{new_filename}'}}
            )
            
            return jsonify({
                'success': True,
                'message': 'Photo uploaded successfully',
                'photoUrl': f'/uploads/{new_filename}'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'File type not allowed'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error uploading photo: {str(e)}'
        }), 500

@app.route('/api/clients', methods=['GET'])
def get_clientss():
    try:
        clients = list(client_details.find())
        
        # Convert ObjectId to string for JSON serialization
        for client in clients:
            client['_id'] = str(client['_id'])
        
        return jsonify({
            'success': True,
            'clients': clients
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving clients: {str(e)}'
        }), 500


@app.route('/api/clients/<client_id>', methods=['GET'])
def get_client(client_id):
    try:
        client = client_details.find_one({'_id': ObjectId(client_id)})
        
        if not client:
            return jsonify({
                'success': False,
                'message': 'Client not found'
            }), 404
            
        # Convert ObjectId to string for JSON serialization
        client['_id'] = str(client['_id'])
        
        return jsonify({
            'success': True,
            'client': client
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving client: {str(e)}'
        }), 500


@app.route('/api/clients/<client_id>', methods=['PUT'])
def update_client(client_id):
    try:
        client_data = request.json
        
        # Add updated timestamp
        client_data['updatedAt'] = datetime.utcnow()
        
        # Update client in database
        result = client_details.update_one(
            {'_id': ObjectId(client_id)},
            {'$set': client_data}
        )
        
        if result.matched_count == 0:
            return jsonify({
                'success': False,
                'message': 'Client not found'
            }), 404
            
        return jsonify({
            'success': True,
            'message': 'Client updated successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error updating client: {str(e)}'
        }), 500



claims = db["claims"]
payments = db["payments"]
payroll = db["payroll"]
timesheet = db["timesheet"]
schedules = db["schedule"]


@app.route('/api/stats/summary', methods=['GET'])
def get_stats_summary():
    # Fetch summary statistics from MongoDB
    unpaid_claims = claims.count_documents({'status': 'unpaid'})
    total_claims = claims.count_documents({})
    
    unpaid_hours = timesheet.aggregate([
        {'$match': {'paid': False}},
        {'$group': {'_id': None, 'total': {'$sum': '$hours'}}}
    ])
    unpaid_hours_value = list(unpaid_hours)[0]['total'] if unpaid_hours.alive else 0
    
    scheduled_hours = schedules.aggregate([
        {'$match': {'date': {'$gte': datetime.now()}}},
        {'$group': {'_id': None, 'total': {'$sum': '$hours'}}}
    ])
    scheduled_hours_value = list(scheduled_hours)[0]['total'] if scheduled_hours.alive else 0
    
    worked_hours = timesheet.aggregate([
        {'$match': {'status': 'approved'}},
        {'$group': {'_id': None, 'total': {'$sum': '$hours'}}}
    ])
    worked_hours_value = list(worked_hours)[0]['total'] if worked_hours.alive else 0
    
    denied_claims = claims.count_documents({'status': 'denied'})
    voided_claims = claims.count_documents({'status': 'voided'})
    replaced_claims = claims.count_documents({'status': 'replaced'})
    
    payroll_paid = payroll.aggregate([
        {'$match': {'status': 'paid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ])
    payroll_paid_value = list(payroll_paid)[0]['total'] if payroll_paid.alive else 0
    
    payroll_total = payroll.aggregate([
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ])
    payroll_total_value = list(payroll_total)[0]['total'] if payroll_total.alive else 0
    
    return jsonify({
        'unpaid_claims': {'count': unpaid_claims, 'total': total_claims},
        'unpaid_hours': unpaid_hours_value,
        'scheduled_hours': scheduled_hours_value,
        'worked_hours': worked_hours_value,
        'denied_claims': {'count': denied_claims, 'total': total_claims},
        'voided_claims': {'count': voided_claims, 'total': total_claims},
        'replaced_claims': {'count': replaced_claims, 'total': total_claims},
        'payroll': {'paid': payroll_paid_value, 'total': payroll_total_value}
    })

@app.route('/api/revenue/yearly', methods=['GET'])
def get_yearly_revenue():
    # Get monthly revenue for the last 12 months
    current_date = datetime.now()
    start_date = current_date - timedelta(days=365)
    
    pipeline = [
        {'$match': {'date': {'$gte': start_date, '$lte': current_date}}},
        {'$group': {
            '_id': {'month': {'$month': '$date'}, 'year': {'$year': '$date'}},
            'revenue': {'$sum': '$amount'}
        }},
        {'$sort': {'_id.year': 1, '_id.month': 1}}
    ]
    
    monthly_revenue = list(payments.aggregate(pipeline))
    
    # Format the result
    result = []
    for entry in monthly_revenue:
        month_year = datetime(entry['_id']['year'], entry['_id']['month'], 1)
        month_name = month_year.strftime('%b %Y')
        result.append({
            'month': month_name,
            'revenue': entry['revenue']
        })
    
    return jsonify(result)

@app.route('/api/payments/by_payer', methods=['GET'])
def get_payments_by_payer():
    # Get payments grouped by payer
    pipeline = [
        {'$group': {
            '_id': '$payer',
            'total': {'$sum': '$amount'}
        }},
        {'$sort': {'total': -1}}
    ]
    
    payments_by_payer = list(payments.aggregate(pipeline))
    
    # Format the result
    result = []
    for entry in payments_by_payer:
        result.append({
            'payer': entry['_id'],
            'amount': entry['total']
        })
    
    return jsonify(result)

@app.route('/api/schedule/caregivers', methods=['GET'])
def get_caregiver_schedule():
    # Get caregiver schedule for the current month
    current_date = datetime.now()
    start_date = datetime(current_date.year, current_date.month, 1)
    if current_date.month == 12:
        end_date = datetime(current_date.year + 1, 1, 1)
    else:
        end_date = datetime(current_date.year, current_date.month + 1, 1)
    
    schedule = list(schedules.find({
        'date': {'$gte': start_date, '$lt': end_date}
    }))
    
    # Convert ObjectId to string for JSON serialization
    for item in schedule:
        item['_id'] = str(item['_id'])
        item['date'] = item['date'].strftime('%Y-%m-%d')
    
    return jsonify(schedule)

@app.route('/api/revenue/by_payer', methods=['GET'])
def get_revenue_by_payer():
    # Get revenue by payer for different time periods
    current_date = datetime.now()
    
    # Time periods
    this_month_start = datetime(current_date.year, current_date.month, 1)
    three_months_ago = current_date - timedelta(days=90)
    six_months_ago = current_date - timedelta(days=180)
    twelve_months_ago = current_date - timedelta(days=365)
    
    # Aggregate revenue by payer for each time period
    payers = payments.distinct('payer')
    result = []
    
    for payer in payers:
        this_month = payments.aggregate([
            {'$match': {'payer': payer, 'date': {'$gte': this_month_start}}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ])
        this_month_value = list(this_month)[0]['total'] if this_month.alive else 0
        
        last_3_months = payments.aggregate([
            {'$match': {'payer': payer, 'date': {'$gte': three_months_ago}}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ])
        last_3_months_value = list(last_3_months)[0]['total'] if last_3_months.alive else 0
        
        last_6_months = payments.aggregate([
            {'$match': {'payer': payer, 'date': {'$gte': six_months_ago}}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ])
        last_6_months_value = list(last_6_months)[0]['total'] if last_6_months.alive else 0
        
        last_12_months = payments.aggregate([
            {'$match': {'payer': payer, 'date': {'$gte': twelve_months_ago}}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ])
        last_12_months_value = list(last_12_months)[0]['total'] if last_12_months.alive else 0
        
        lifetime = payments.aggregate([
            {'$match': {'payer': payer}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ])
        lifetime_value = list(lifetime)[0]['total'] if lifetime.alive else 0
        
        result.append({
            'payer': payer,
            'this_month': this_month_value,
            'last_3_months': last_3_months_value,
            'last_6_months': last_6_months_value,
            'last_12_months': last_12_months_value,
            'lifetime': lifetime_value
        })
    
    return jsonify(result)


employee_details = db["employee_details"]

# Configure upload folder for employee profile images
UPLOAD_FOLDER = 'static/uploads/employees'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/save-employee', methods=['POST'])
def save_employee():
    try:
        # Get data from request
        employee_data = request.json
        
        # Add creation timestamp
        employee_data['createdAt'] = datetime.utcnow()
        
        # Insert data into MongoDB
        result = employee_details.insert_one(employee_data)
        
        # Return success response with the created employee ID
        return jsonify({
            'success': True,
            'message': 'Employee data saved successfully',
            'employeeId': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        # Return error response
        return jsonify({
            'success': False,
            'message': f'Error saving employee data: {str(e)}'
        }), 500


@app.route('/api/upload-profile-image/<employee_id>', methods=['POST'])
def upload_profile_image(employee_id):
    try:
        # Check if an employee with this ID exists
        employee = employee_details.find_one({'_id': ObjectId(employee_id)})
        if not employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404

        # Check if the post request has the file part
        if 'profileImage' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file part in the request'
            }), 400
            
        file = request.files['profileImage']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No selected file'
            }), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add employee ID to filename to ensure uniqueness
            new_filename = f"emp_{employee_id}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            file.save(file_path)
            
            # Update employee record with photo path
            employee_details.update_one(
                {'_id': ObjectId(employee_id)},
                {'$set': {'profileImageUrl': f'/uploads/employees/{new_filename}'}}
            )
            
            return jsonify({
                'success': True,
                'message': 'Profile image uploaded successfully',
                'profileImageUrl': f'/uploads/employees/{new_filename}'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'File type not allowed'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error uploading profile image: {str(e)}'
        }), 500


@app.route('/api/employees', methods=['GET'])
def get_employees():
    try:
        employees = list(employee_details.find())
        
        # Convert ObjectId to string for JSON serialization
        for employee in employees:
            employee['_id'] = str(employee['_id'])
        
        return jsonify({
            'success': True,
            'employees': employees
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving employees: {str(e)}'
        }), 500


@app.route('/api/employees/<employee_id>', methods=['GET'])
def get_employee(employee_id):
    try:
        employee = employee_details.find_one({'_id': ObjectId(employee_id)})
        
        if not employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404
            
        # Convert ObjectId to string for JSON serialization
        employee['_id'] = str(employee['_id'])
        
        return jsonify({
            'success': True,
            'employee': employee
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving employee: {str(e)}'
        }), 500


@app.route('/api/employees/<employee_id>', methods=['PUT'])
def update_employee(employee_id):
    try:
        employee_data = request.json
        
        # Add updated timestamp
        employee_data['updatedAt'] = datetime.utcnow()
        
        # Update employee in database
        result = employee_details.update_one(
            {'_id': ObjectId(employee_id)},
            {'$set': employee_data}
        )
        
        if result.matched_count == 0:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404
            
        return jsonify({
            'success': True,
            'message': 'Employee updated successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error updating employee: {str(e)}'
        }), 500


@app.route('/api/employees/<employee_id>', methods=['DELETE'])
def delete_employee(employee_id):
    try:
        # Find employee first to get profile image path if exists
        employee = employee_details.find_one({'_id': ObjectId(employee_id)})
        
        if not employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404
            
        # Delete employee profile image if it exists
        if 'profileImageUrl' in employee:
            image_path = os.path.join(
                app.root_path, 
                employee['profileImageUrl'].lstrip('/')
            )
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # Delete employee from database
        result = employee_details.delete_one({'_id': ObjectId(employee_id)})
        
        return jsonify({
            'success': True,
            'message': 'Employee deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting employee: {str(e)}'
        }), 500


care_plans_collection = db['care_plans']

@app.route('/save-care-plan', methods=['POST'])
def save_care_plan():
    try:
        # Get JSON data from request
        care_plan_data = request.json

        # Add timestamp
        care_plan_data['created_at'] = datetime.utcnow()

        # Insert into MongoDB
        result = care_plans_collection.insert_one(care_plan_data)

        # Return success response with inserted ID
        return jsonify({
            'message': 'Care Plan saved successfully',
            'id': str(result.inserted_id)
        }), 201

    except Exception as e:
        # Handle potential errors
        return jsonify({
            'message': 'Error saving Care Plan',
            'error': str(e)
        }), 500

@app.route('/get-care-plans', methods=['GET'])
def get_care_plans():
    try:
        # Retrieve all care plans
        care_plans = list(care_plans_collection.find())
        
        # Convert ObjectId to string for JSON serialization
        for plan in care_plans:
            plan['_id'] = str(plan['_id'])

        return jsonify(care_plans), 200

    except Exception as e:
        return jsonify({
            'message': 'Error retrieving Care Plans',
            'error': str(e)
        }), 500
    
@app.route('/careplan')
def careplan():
    """
    Redirect to the root.
    """
    user = session.get('user')
    return render_template('careplan.html', user=user)


client_details_collection = db['client_details']

@app.route('/get-clients', methods=['GET'])
def get_clients():
    try:
        # Retrieve client details
        clients = list(client_details_collection.find())
        
        # Transform client data to include full name and other relevant info
        client_list = []
        for client_info in clients:
            # Construct full name
            full_name = " ".join(filter(bool, [
                client_info.get('firstName', ''),
                client_info.get('middleName', ''),
                client_info.get('lastName', '')
            ])).strip()
            
            # If full name is empty, use preferred name or fall back to other identifiers
            if not full_name:
                full_name = client_info.get('preferredName', '')
            
            # If still no name, use member ID
            if not full_name:
                full_name = client_info.get('memberId', 'Unnamed Client')
            
            client_list.append({
                'id': str(client_info['_id']),
                'fullName': full_name,
                'status': client_info.get('status', ''),
                'memberId': client_info.get('memberId', ''),
                'referralSource': client_info.get('referralSource', '')
            })

        return jsonify(client_list), 200

    except Exception as e:
        return jsonify({
            'message': 'Error retrieving Client Names',
            'error': str(e)
        }), 500

@app.route('/get-client-details/<client_id>', methods=['GET'])
def get_client_details(client_id):
    try:
        # Retrieve specific client details
        client_details = client_details_collection.find_one({'_id': ObjectId(client_id)})
        
        if not client_details:
            return jsonify({'message': 'Client not found'}), 404
        
        # Convert ObjectId to string
        client_details['_id'] = str(client_details['_id'])
        
        return jsonify(client_details), 200

    except Exception as e:
        return jsonify({
            'message': 'Error retrieving Client Details',
            'error': str(e)
        }), 500

@app.route('/api/get-schedules', methods=['GET'])
@login_required
def get_schedules():
    schedules = list(schedules.find())
    for schedule in schedules:
        schedule['_id'] = str(schedule['_id'])  # Convert ObjectId to string
    return jsonify(schedules)

@app.route('/api/approve-schedule/<schedule_id>', methods=['POST'])
@login_required
def approve_schedule(schedule_id):
    result = schedules.update_one(
        {'_id': ObjectId(schedule_id)},
        {'$set': {'status': 'Approved'}}
    )
    if result.modified_count > 0:
        return jsonify({'message': 'Schedule approved successfully!'})
    return jsonify({'message': 'Failed to approve schedule.'}), 400

@app.route('/api/reject-schedule/<schedule_id>', methods=['POST'])
@login_required
def reject_schedule(schedule_id):
    result = schedules.update_one(
        {'_id': ObjectId(schedule_id)},
        {'$set': {'status': 'Rejected'}}
    )
    if result.modified_count > 0:
        return jsonify({'message': 'Schedule rejected successfully!'})
    return jsonify({'message': 'Failed to reject schedule.'}), 400


@app.route('/schedule-approval', methods=['GET'])
def schedule_approval():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('schedule-approval.html', user=user)

@app.route('/daily_schedule', methods=['GET'])
def daily_schedule():
    """
    Render the Terms of Service page.
    """

    user = session.get('user')
    return render_template('daily_schedule.html', user=user)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)







# Converted monolithic to proper directory structure for easy debugging

# main.py
# from flask import Flask
# import os
# import logging
# import sys
# from pathlib import Path

# # Add the project root directory to Python path
# project_root = Path(__file__).parent
# sys.path.append(str(project_root))

# from routes.auth import auth_bp
# from routes.file import file_bp
# from routes.main import main_bp
# from config import Config

# def create_app():
#     app = Flask(__name__)
    
#     # Load configuration
#     app.config.from_object(Config)
    
#     # Configure logging
#     app.logger.setLevel(logging.INFO)
    
#     # Create upload folder if it doesn't exist
#     if not os.path.exists(app.config['UPLOAD_FOLDER']):
#         os.makedirs(app.config['UPLOAD_FOLDER'])
    
#     # Register blueprints
#     app.register_blueprint(auth_bp)
#     app.register_blueprint(file_bp)
#     app.register_blueprint(main_bp)
    
#     return app

# if __name__ == '__main__':
#     app = create_app()
#     app.run(debug=True)


# chat history

# lets have for a document every user have 1 user Document

# Chat histroy would be an object

# an array
# {
#     chat_respone:
#     Files_invloved:
# }