import pandas as pd
import requests
from config import API_KEY # Ensure you have your API key in a config file or environment variable
from datetime import datetime, time
from models import Agency, HoursOfOperation, WraparoundService, CultureServed

from database import init_db, session

def get_lat_lon(address):
    api_key = API_KEY
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    
    response = requests.get(url)
    data = response.json()
    
    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None

# Step 1: Initialize DB (create tables if they don’t exist)
init_db()

# Helpers
def parse_time(time_str):
    """Converts a time string to a `datetime.time` object if valid, otherwise returns None."""
    if isinstance(time_str, time):  # If it's already a time object, return it
        return time_str
    elif isinstance(time_str, str):  # If it's a string, check if it's a valid time
        time_str = time_str.strip()
        try:
            return datetime.strptime(time_str, "%I:%M %p").time()
        except ValueError:  # If parsing fails, return None (or handle differently)
            return None
    else:
        return None  # Handle unexpected types


def parse_bool(val):
    if isinstance(val, str):
        return val.strip().lower() == 'yes'
    return bool(val)

# ========== MARKETS ==========
df_markets_hoo = pd.read_excel('data/CAFB_Markets_HOO.xlsx')
for _, row in df_markets_hoo.iterrows():
    agency_id = row['Agency ID']
    agency_name = row['Agency Name']
    shipping_address = row['Shipping Address']
    existing = session.query(Agency).filter_by(id=agency_id).first()
    if not existing:
        lat, lon = get_lat_lon(shipping_address)
        agency = Agency(agency_id=agency_id, name=agency_name, type='market', address = shipping_address, phone=None, latitude=lat, longitude=lon)
        session.add(agency)

    hours = HoursOfOperation(
        agency_id=agency_id,
        day_of_week=row['Day of Week'],
        start_time=parse_time(row['Starting Time']),
        end_time=parse_time(row['Ending Time']),
        frequency=row['Frequency'],
        distribution_model=row.get('Distribution Models'),
        food_format=row.get('Food Format '),
        pantry_requirements=row.get('Food Pantry Requirements'),
        appointment_only=None  # No such field in this sheet
    )
    session.add(hours)

df_markets_services = pd.read_excel('data/CAFB_Markets_Wraparound_Services.xlsx')
for _, row in df_markets_services.iterrows():
    service = WraparoundService(agency_id=row['Agency ID'], service=row['Wraparound Service'])
    session.add(service)

df_markets_cultures = pd.read_excel('data/CAFB_Markets_Cultures_Served.xlsx')
for _, row in df_markets_cultures.iterrows():
    cultures = row['Cultural Populations Served']
    entry = CultureServed(agency_id=row['Agency ID'], cultures=cultures)
    session.add(entry)

# ========== SHOPPING PARTNERS ==========
df_sp_hoo = pd.read_excel('data/CAFB_Shopping_Partners_HOO.xlsx')
for _, row in df_sp_hoo.iterrows():
    agency_id = row['External ID']
    agency_name = row['Name']
    shipping_address = row['Shipping Address']
    phone = row['Phone']
    existing = session.query(Agency).filter_by(id=agency_id).first()
    if not existing:
        lat, lon = get_lat_lon(shipping_address)
        agency = Agency(agency_id=agency_id, name=agency_name, type='shopping_partner', address = shipping_address, phone=phone, latitude=lat, longitude=lon)
        session.add(agency)

    hours = HoursOfOperation(
        agency_id=agency_id,
        day_of_week=row['Day of Week'],
        start_time=parse_time(row['Starting Time']),
        end_time=parse_time(row['Ending Time']),
        frequency=row['Monthly Options'],
        appointment_only=parse_bool(row['By Appointment Only']),
        pantry_requirements=row.get('Food Pantry Requirements'),
        distribution_model=row.get('Distribution Models'),
        food_format=row.get('Food Format ')
    )
    session.add(hours)

df_sp_services = pd.read_excel('data/CAFB_Shopping_Partners_Wraparound_Services.xlsx')
for _, row in df_sp_services.iterrows():
    service = WraparoundService(agency_id=row['Agency ID'], service=row['Wraparound Service'])
    session.add(service)

df_sp_cultures = pd.read_excel('data/CAFB_Shopping_Partners_Cultures_Served.xlsx')
for _, row in df_sp_cultures.iterrows():
    cultures = row['Cultural Populations Served']
    entry = CultureServed(agency_id=row['Agency ID'], cultures=cultures)
    session.add(entry)

# Commit everything
session.commit()
session.close()
