import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json

# Initialize Google Sheets
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('./ecotourism-perso-iti-d4b614608bab.json', scopes)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key("1hc4ArEdETsxuGC0aWddBZ7WN00OjuNjbVispnuk9Urs")
matrix_sheet = spreadsheet.worksheet("Regions")

# Load data from the first sheet
sheet = spreadsheet.sheet1
data = sheet.get_all_records()

# Extract GPS coordinates and IDs
locations = [entry['GPS'].replace(" ", "") for entry in data]
ids = [str(entry['ID']) for entry in data]

# Function to get travel times between locations using OSRM
def get_travel_times(locations):
    osrm_route_url = "http://router.project-osrm.org/route/v1/driving/"
    n = len(locations)
    travel_times_matrix = [["" for _ in range(n)] for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            if i == j:
                travel_times_matrix[i][j] = "0 mins"
                continue
            coordinates = f"{locations[i]};{locations[j]}"
            url = osrm_route_url + coordinates + "?overview=false"
            response = requests.get(url)
            data = response.json()
            if data['code'] == 'Ok':
                duration = data['routes'][0]['duration'] / 60
                travel_times_matrix[i][j] = f"{int(duration)} mins"
            else:
                travel_times_matrix[i][j] = "N/A"
    return travel_times_matrix

travel_times_matrix = get_travel_times(locations)

# Check if the matrix sheet exists, or create it
try:
    matrix_sheet = spreadsheet.worksheet("Travel Times Matrix")
except gspread.exceptions.WorksheetNotFound:
    matrix_sheet = spreadsheet.add_worksheet(title="Travel Times Matrix", rows="100", cols="20")

# Write the matrix to the new sheet with IDs
headers = ['ID'] + ids
matrix_with_ids = [headers] + [[ids[i]] + row for i, row in enumerate(travel_times_matrix)]
matrix_sheet.clear()
matrix_sheet.update('A1', matrix_with_ids)

print("Travel Times Matrix has been successfully stored in the spreadsheet.")
