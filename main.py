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

    # Prepare the payload for the OpenAI API request
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
                    {"role": "system", "content": (
    "You are an AI assistant tasked with creating a personalized one-day itinerary that you will send by email for a first-time visitor to Mauritius, "
    "who is interested in ecotourism. Your response should be user-friendly and easy to understand, avoiding technical details like GPS points and precise travel times. Be approximate on these as a toursit is here to enjoy, not racing.   "
    "The itinerary should include a diverse set of activities based on the user's interests, budget, and dietary preferences, and avoid redundancy in activity types (e.g., not more than one beach or museum unless specified by user interests). "
    "Ensure the total itinerary time is under 8 hours and that the route is efficient, avoiding backtracking or redundant paths. Here's what you should include:\n"
    "1. Morning: Suggest 1-3 activities that match the user's interests. Include the travel times between these activities.\n"
    "2. Lunch: Recommend a place for lunch that is near the last morning activity and suits the user's dietary preferences, and indicate the travel time from the last morning activity. Do not invent a restaurant. \n"
    "3. Afternoon: Suggest 1-3 more activities, ensuring they logically follow the lunch location without backtracking.\n"
    "4. Dinner: Recommend a dinner spot, considering dietary preferences, with travel time from the last afternoon activity.\n"
    "5. Summarize the total travel time and any other relevant information for an enjoyable day. "
    "Note: Volunteering and conservation activities are special; include a note after the itinerary that the user must contact the respective organizations to arrange participation."
    "You have to return the itierary structures, in an email format with the needed tags etc"
    
)},

            {"role": "user", "content": f"User interests: {interests}, budget range: {budget_range}, dietary preferences: {dietary}."},
            {"role": "user", "content": f"Activities: {json.dumps(data)}"},
            
            {"role": "user", "content": f"Travel times matrix for region (each activity has its associated region ID): {json.dumps(matrix)}"}
            

        ],
        "temperature": 0.3,
        "max_tokens": 600  # Increase this value as needed, but be mindful of the limits
        
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
