from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import requests
import json

app = Flask(__name__)

# Set up Google Sheets access
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('./ecotourism-perso-iti-d4b614608bab.json', scopes=scopes)
gspread_client = gspread.authorize(creds)
sheet = gspread_client.open_by_key("1nHhzTxhJFiNhnEuzYgcBLf955bSUHQLkHOybTXpVq7o").sheet1

def load_knowledge_base():
    # Load all records from the sheet into a list of dictionaries
    return sheet.get_all_records()

knowledge_base = load_knowledge_base()

def parse_budget(budget_range):
    """ Convert budget range string to numerical min and max values. """
    if budget_range == "Moderate ($100-$200)":
        return (100, 200)
    # Add more cases as needed
    return (0, float('inf'))  # Default to no budget limit

@app.route('/generate-itinerary', methods=['POST'])
def generate_itinerary():
    data = request.json
    interests = data.get('interests', [])
    budget_range = data.get('budget', "Moderate ($100-$200)")
    dietary = data.get('dietary', 'Any')
    min_budget, max_budget = parse_budget(budget_range)

    # Load and filter activities from the knowledge base based on user preferences
    filtered_activities = [
        activity for activity in knowledge_base
        if activity.get('Type', '') in interests and min_budget <= activity.get('Cost', float('inf')) <= max_budget and (activity.get('Dietary', 'Any') == dietary or not dietary)
    ]

    # Prepare the payload for the OpenAI API request
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": f"Create a personalized itinerary based on these activities: {filtered_activities}"}],
        "temperature": 0.7
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-proj-34sTLTYrblw1BilxkgIVT3BlbkFJq2R2uyXj5PdIjEv0kSCE"
    }

    try:
        # Send the POST request to OpenAI
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response_json = response.json()
        print(response_json)
        if 'choices' in response_json and response_json['choices']:
            messages = response_json['choices'][0]['message']['content']
            itinerary = ''.join([msg['content'] for msg in messages if msg['role'] == 'assistant'])
            return jsonify({"itinerary": itinerary})
        else:
            return jsonify({"error": "No itinerary generated"})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
