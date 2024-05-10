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
spreadsheet = gspread_client.open_by_key(os.getenv("SHEET_KEY"))

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

    system_prompt = (
    "You are creating a personalized one-day itinerary in HTML format for a visitor to Mauritius interested in ecotourism. "
    "The itinerary should be engaging and easy to follow, avoiding overly technical details. Use approximate travel times. "
    "The day's activities should vary, avoiding repetitive types unless specifically requested by the user. Ensure the entire day's activities, including travel, fit within 8 hours, avoiding inefficient routing. "
    "Your HTML email content should start with '<!DOCTYPE html>' and end with '</html>'. Here are the key components to include:\n"
    "1. Morning: List 1-3 activities that align with the user's interests, keeping total time under 5 hours including travel.\n"
    "2. Lunch: Suggest a dining spot near the last morning activity that fits the dietary preferences, without inventing a place.\n"
    "3. Afternoon: Recommend 1-3 activities post-lunch, ensuring logical sequence from the dining spot. If adding a sunset at a beach, the total time can extend slightly.\n"
    "4. Dinner: Propose a place for dinner based on dietary needs and close to the last activity.\n"
    "5. Summary: Provide the total travel time and any additional tips for a pleasant day. "
    "Note: Mention that volunteering and conservation require prior arrangement with the organizations. "
    "Avoid indicating you are an AI. Focus on creating a concise, enjoyable plan for the user."
)

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User interests: {interests}, budget range: {budget_range}, dietary preferences: {dietary}."},
            {"role": "user", "content": f"Activities: {json.dumps(data)}"},
            {"role": "user", "content": f"Travel times matrix for region (each activity has its associated region ID): {json.dumps(matrix)}"}
        ],
        "temperature": 0.3
    }

    print("Loaded API Key:", os.getenv('OPENAI_API_KEY'))
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
    }
    
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response_json = response.json()
    print(json.dumps(response_json, indent=4))
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
