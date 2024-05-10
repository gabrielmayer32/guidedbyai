from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import requests
import json
import os
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Set up Google Sheets access
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(os.getenv('GOOGLE_CREDENTIALS_FILE'), scopes=scopes)
gspread_client = gspread.authorize(creds)
spreadsheet = gspread_client.open_by_key("1hc4ArEdETsxuGC0aWddBZ7WN00OjuNjbVispnuk9Urs")

# Load data from the spreadsheet
data_sheet = spreadsheet.sheet1
data = data_sheet.get_all_records()

# Load the travel times matrix from another sheet
matrix_sheet = spreadsheet.worksheet("Travel Times Matrix")
matrix_data = matrix_sheet.get_all_values()
ids = matrix_data[0][1:]  # First row, starting from second column
matrix = {int(row[0]): {int(ids[i]): row[i+1] for i in range(len(ids))} for row in matrix_data[1:]}

def safe_convert_to_int(value, default=float('inf')):
    """ Safely convert a value to an integer, using default if conversion fails. """
    try:
        return int(value)
    except ValueError:
        return default
    
def parse_budget(budget_range):
    """ Convert budget range string to numerical min and max values. """
    if budget_range == "Moderate ($100-$200)":
        return (100, 200)
    # Add more cases as needed
    return (0, float('inf'))

def generate_itinerary(interests, budget_range, dietary):
    min_budget, max_budget = parse_budget(budget_range)

    # Filter activities based on user preferences
    filtered_activities = [
        activity for activity in data
        if any(tag in activity.get('Tags', '').split(', ') for tag in interests) and
           min_budget <= safe_convert_to_int(activity.get('Cost', 'inf')) <= max_budget and
           (activity.get('Dietary', 'Any') == dietary or not dietary)
    ]

    # Prepare the payload for the OpenAI API request
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are an assistant tasked with creating a personalized one-day itinerary. The recipient of this message is a first-time visitor to the area who is interested in ecotourism. They have provided the following information to help you create the itinerary. You are writing back to them with the itinerary. \
             bare in mind that it is an end user reading it so don't put any technical details, gps point or any other technical information."},
            {"role": "user", "content": f"User interests: {interests}, budget range: {budget_range}, dietary preferences: {dietary}."},
            {"role": "user", "content": f"Activities: {json.dumps(data)}"},
            {"role": "user", "content": f"Travel times matrix: {json.dumps(matrix)}"}
        ],
        "temperature": 0.3
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response_json = response.json()
    
    if 'choices' in response_json and response_json['choices']:
        message_content = response_json['choices'][0]['message']['content']
        return message_content
    else:
        return "No itinerary generated"

@app.route('/create-itinerary', methods=['POST'])
def api_generate_itinerary():
    data = request.json
    interests = data.get('interests', [])
    budget_range = data.get('budget', "Moderate ($100-$200)")
    dietary = data.get('dietary', 'Any')
 
    itinerary = generate_itinerary(interests, budget_range, dietary)
    return jsonify({"itinerary": itinerary})

if __name__ == '__main__':
    app.run(debug=True)
