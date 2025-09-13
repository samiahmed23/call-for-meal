from flask import Blueprint, request, jsonify, render_template, Flask
from database import get_connection
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import logging
import json
import requests
from pydantic import BaseModel, ValidationError
from typing import List, Dict, Union
from config import API_KEY
from datetime import datetime
# from vapi_python import Vapi

api_blueprint = Blueprint("api", __name__)

# vapi = Vapi(api_key="5f2acde3-9ffb-46c7-ac07-ab4628e52146")
# Configure logging
logging.basicConfig(level=logging.INFO)

# ----------------------------
# Utility Functions
# ----------------------------

def get_lat_lon(address):
    api_key = API_KEY
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    
    response = requests.get(url)
    data = response.json()
    
    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None

def calculate_distance(lat1, lon1, lat2, lon2):
    return round(geodesic((lat1, lon1), (lat2, lon2)).miles, 2)

from datetime import datetime
import logging

def format_time_12hr(time_str):
    if not time_str:
        return None
    try:
        # Try with microseconds
        time_obj = datetime.strptime(time_str, "%H:%M:%S.%f").time()
    except ValueError:
        try:
            # Fallback to without microseconds
            time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        except Exception as e:
            logging.error(f"Time formatting error: {e}")
            return None

    return time_obj.strftime("%I:%M %p").lstrip("0")


def generate_voice_summary(agencies, day_of_week):
    if not agencies:
        return f"I couldn't find any food sites open on {day_of_week}. Would you like to try a different day?"

    summary = f"I found {len(agencies)} food site{'s' if len(agencies) > 1 else ''} near you for {day_of_week}. "

    for agency in agencies:
        name = agency['name'].split(':')[1].strip() if ':' in agency['name'] else agency['name']
        address = agency['address'].replace("Attn:", "").strip()
        start_time = format_time_12hr(agency['start_time']) if agency['start_time'] else None
        end_time = format_time_12hr(agency['end_time']) if agency['end_time'] else None
        appointment = "Appointments are required" if agency.get('appointment_only') else "Walk-ins are welcome"
        cultures = f"Serves: {', '.join(agency['cultures_served'])}" if agency.get('cultures_served') else None
        distance = f"about {agency['distance']} miles away" if agency.get('distance') else None
        model = agency.get('distribution_model')
        food_format = agency.get('food_format')
        frequency = agency.get('frequency')
        requirements = agency.get('pantry_requirements')
        phone = agency.get('phone')
        wraparound = agency.get('wraparound_services')

        # Time phrase
        if start_time and end_time:
            time_phrase = f"open from {start_time} to {end_time}"
        # elif start_time and (end_time == None):
        #     time_phrase = f"open from {start_time}"
        # elif (start_time == None) and end_time:
        #     time_phrase = f"open until {end_time}"
        else:
            time_phrase = "operating hours are currently not available"
            
        print(agency['name'], agency['start_time'], agency['end_time'])

        # Conversational extras summary
        extras_sentences = []

        if distance:
            extras_sentences.append(f"It's about {agency['distance']} miles away.")
        if model:
            extras_sentences.append(f"It's a {model.lower()} site.")
        if food_format:
            extras_sentences.append(f"They offer {food_format.lower()}.")
        if frequency:
            extras_sentences.append(f"This site operates {frequency.lower()}.")
        if requirements:
            extras_sentences.append("You may need an ID or meet other requirements.")
        if cultures:
            extras_sentences.append(f"This site serves communities including {', '.join(agency['cultures_served'])}.")
        if wraparound:
            extras_sentences.append("Wraparound services are also available.")
        if phone:
            extras_sentences.append(f"If you have questions, you can call them at {phone}.")

        extras_phrase = " ".join(extras_sentences)

        summary += f"{name}, located at {address}, is {time_phrase}. {appointment}. {extras_phrase}. "

    summary += "Would you like directions or to hear more options?"
    return summary

# ----------------------------
# Routes
# ----------------------------

@api_blueprint.route("/", methods=["GET"])
def home_page():
    return render_template("home.html")

@api_blueprint.route("/app", methods=["GET"])
def app_page():
    return render_template("index.html", api_key=API_KEY)

@api_blueprint.route("/donate", methods=["GET"])
def donate_page():
    return render_template("donate.html")

@api_blueprint.route("/agencies", methods=["GET"])
def get_agencies():
    try:
        conn = get_connection()
        cursor = conn.execute("SELECT DISTINCT agency_id, name FROM agencies;")
        agencies = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        conn.close()
        return jsonify(agencies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_blueprint.route("/agencies/<string:agency_id>", methods=["GET"])
def get_agency(agency_id):
    
    conn = get_connection()
    cursor = conn.cursor()
    
    agency = cursor.execute("SELECT * FROM agencies WHERE agency_id = ?", (agency_id,))
    
    conn.close()
    if agency:
        return jsonify({
            "agency_id": agency.agency_id,
            "name": agency.name,
            "type": agency.type,
            "address": agency.address,
            "phone": agency.phone
        })
    return jsonify({"error": "Agency not found"}), 404

@api_blueprint.route("/search", methods=["GET"])
def search_agencies():
    address = request.args.get("address")  # Get address or ZIP code
    radius = float(request.args.get("radius", 5))  # Default radius = 5 miles
    lat = request.args.get("lat")  # If user selects to filter from their current location
    lng = request.args.get("lng") # If user selects to filter from their current location
    day = request.args.get("day")  # Day of the week for filtering
    home_delivery = request.args.get("homeDelivery") == "true"  # Home delivery option
    
    # if not address:
    #     return jsonify({"error": "Address is required"}), 400


    # geolocator = Nominatim(user_agent="food_assistance_locator")
    # location = geolocator.geocode(address, country_codes="us") # Limit to US locations
    
    if address:
         # Convert address(zipcode to be precise) to lat/lon 
        geolocator = Nominatim(user_agent="food_assistance_locator")
        location = geolocator.geocode(address,  country_codes="us") # Limit to US locations 
        
        if not location:
            return jsonify({"error": "Location not found"}), 404
        user_coords = (location.latitude, location.longitude)
    elif lat and lng: # If user gave the site their current location
        user_coords = (float(lat), float(lng))    
    else:
        return jsonify({"error": "Address or coordinates are required"}), 400
    
    conn = get_connection()
    cursor = conn.cursor()

    # This query retrieves all necessary agency data with joins
    agencies = cursor.execute("""SELECT a.agency_id, a.name, a.type, a.address, a.phone, a.latitude, a.longitude,
                   h.day_of_week, h.start_time, h.end_time ,h.distribution_model, h.food_format, h.appointment_only, h.pantry_requirements,
                   w.service, c.cultures
            FROM agencies a
            JOIN hours_of_operation h ON a.agency_id = h.agency_id
            LEFT JOIN wraparound_services w ON a.agency_id = w.agency_id
            LEFT JOIN cultures_served c ON a.agency_id = c.agency_id""")
    conn.close()
    
    nearby_agencies = []
    

    for agency in agencies:
        agency_id, name, type, address, phone, latitude, longitude, day_of_week, start_time, end_time, distribution, food_format, appointment, pantry_req, wrap_service, culture = agency  # unpack tuple
        agency_coords = (latitude, longitude)
        distance = geodesic(user_coords, agency_coords).miles  # Calculate distance
        
        
        if day_of_week is None:
            day_of_week = "Null"

        if distance <= radius and (day_of_week.lower() == day.lower() or day_of_week.lower() == "As Needed"):  # Check if the agency is within the radius and matches the day of the week
            # Only include agencies that match the day of the week and within the radius
            
            
            #### These will be used to in the location info window (fixing some inconsistencies in the database) ####
            
            
            # Prepared meals availability
            
            if food_format is None:
                food_format = "N/A"
            if "Prepared meals" in food_format:
                food_format = "Available✅"
            else:
                food_format = "Not available❌"
        
            
            # Appointment requirements
            
            if appointment is None:
                appointment = "N/A"
            if appointment == 1:
                appointment = "Required⚠️"
            else:
                appointment = "Not required✅"    
            
            
            
            # Home delivery availability
            if distribution is None:
                distribution = "N/A"
            if "Home Delivery" in distribution:
                hd_status = "Available✅"
            else:
                hd_status = "Not available❌"   
                
                
            # Start and end times
            if start_time is None:
                start_time = "N/A"     
            if end_time is None:
                end_time = "N/A"
            open_hours = start_time[:5] + " - " + end_time[:5]
            
            
            # Dealing with address inconsistencies ('Attn:' prefix in some addresses)
            if address[:5] == "Attn:":
                address = address[5:]
                    
                
            if "Home Delivery" in distribution and home_delivery:   # Only include agencies that offer home delivery if the user selected that option
                nearby_agencies.append({
                "id": agency_id,
                "name": name.split(':')[1].strip() if ':' in name else name,
                "latitude": latitude,
                "longitude": longitude,
                "distance": round(distance, 2),
                "phone": phone if phone else "No phone number available",
                "day": day_of_week,
                "Prepared_meals": food_format,
                "appointment": appointment,
                "home_delivery": hd_status,
                "address": address,
                "hours": open_hours
                
            })
                
            
            elif not home_delivery: # If the user did not select home delivery, include all agencies that match the day of the week and are within the radius
            
                nearby_agencies.append({
                    "id": agency_id,
                    "name": name.split(':')[1].strip() if ':' in name else name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "distance": round(distance, 2),
                    "phone": phone if phone else "No phone number available",
                    "day": day_of_week,
                    "Prepared_meals": food_format,
                    "appointment": appointment,
                    "home_delivery": hd_status,
                    "address": address,
                    "hours": open_hours
                    
                    
                })
            
        
    
    return jsonify(nearby_agencies)

# ----------------------------
# Expert Query Route (Browser)
# ----------------------------

@api_blueprint.route("/expertquery", methods=["GET"])
def get_filtered_agencies():
    try:
        address = request.args.get("address")
        day_of_week = request.args.get("day_of_week")
        max_distance = float(request.args.get("max_distance", 5.0))

        user_lat, user_lon = get_lat_lon(address)
        if not user_lat or not user_lon:
            return jsonify({"error": "Invalid location"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        # This query retrieves all necessary agency data with joins
        cursor.execute("""
            SELECT a.agency_id, a.name, a.type, a.address, a.phone, a.latitude, a.longitude,
                   h.day_of_week, h.start_time, h.end_time, h.frequency,
                   h.distribution_model, h.food_format, h.appointment_only, h.pantry_requirements,
                   w.service, c.cultures
            FROM agencies a
            JOIN hours_of_operation h ON a.agency_id = h.agency_id
            LEFT JOIN wraparound_services w ON a.agency_id = w.agency_id
            LEFT JOIN cultures_served c ON a.agency_id = c.agency_id
            WHERE lower(h.day_of_week) = ?
        """, (day_of_week.lower(),))

        agency_map = {}

        for row in cursor.fetchall():
            (
                aid, name, typ, address, phone, lat, lon,
                dow, start, end, freq, model, fmt, appt, pantry,
                service, culture
            ) = row

            distance = calculate_distance(user_lat, user_lon, lat, lon)
            if distance > max_distance:
                continue

            if aid not in agency_map:
                agency_map[aid] = {
                    "id": aid,
                    "name": name,
                    "type": typ,
                    "address": address,
                    "phone": phone,
                    "latitude": lat,
                    "longitude": lon,
                    "distance": round(distance, 2),
                    "day_of_week": dow,
                    "start_time": start,
                    "end_time": end,
                    "frequency": freq,
                    "distribution_model": model,
                    "food_format": fmt,
                    "appointment_only": bool(appt),
                    "pantry_requirements": pantry,
                    "wraparound_services": set(),
                    "cultures_served": set()
                }

            if service:
                agency_map[aid]["wraparound_services"].add(service)
            if culture:
                agency_map[aid]["cultures_served"].add(culture)

        # Final cleanup and formatting
        result = []
        for agency in agency_map.values():
            agency["wraparound_services"] = list(agency["wraparound_services"])
            agency["cultures_served"] = list(agency["cultures_served"])
            result.append(agency)

        result.sort(key=lambda x: x["distance"])
        conn.close()
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Expert Query Error: {e}")
        return jsonify({"error": str(e)}), 500


# ----------------------------
# VAPI Tool API Route
# ----------------------------

class ToolCallFunction(BaseModel):
    name: str
    arguments: Union[str, Dict]

class ToolCall(BaseModel):
    id: str
    function: ToolCallFunction

class Message(BaseModel):
    toolCalls: List[ToolCall]

class VapiRequest(BaseModel):
    message: Message

@api_blueprint.route("/vapi_expertquery", methods=["POST"])
def vapi_tool_handler():
    try:
        print("Received tool call from VAPI 1:", request)

        payload = request.get_json(force=True)
        # print("Payload received:", payload)

        data = VapiRequest(**payload)

        for tool_call in data.message.toolCalls:
            if tool_call.function.name == "getFoodSites":
                args = tool_call.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)

                address = args["address"]
                day_of_week = args["day_of_week"]

                # Simulate query string for reuse
                request.args = {
                    "address": address,
                    "day_of_week": day_of_week
                }

                # Get response and status from existing function
                response, status_code = get_filtered_agencies()
                response_data = response.get_json()
                
                summary = generate_voice_summary(response_data, day_of_week.title())

                return jsonify({
                    "results": [{
                        "toolCallId": tool_call.id,
                        "result": summary
                    }]
                }), 200

        return jsonify({"error": "No matching tool call found"}), 400

    except ValidationError as e:
        logging.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        logging.error(f"Exception in /vapi_expertquery: {e}")
        return jsonify({"error": str(e)}), 500

# # Start the call
# @api_blueprint.route('/start_call', methods=["POST"])
# def start_call():
#     try:
#         vapi.start(assistant_id='df71a9ab-c83c-4497-adbd-6fb95f01f8eb')
#         return jsonify({"status": "call started"}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# # Stop the call
# @api_blueprint.route('/stop_call', methods=["POST"])
# def stop_call():
#     try:
#         vapi.stop()
#         return jsonify({"status": "call stopped"}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
    

@api_blueprint.route('/outbound', methods=['POST'])
def outbound_route():
    data = request.get_json()  # Extract data from the request body

    try:
        response = requests.post(
            "https://api.vapi.ai/call/phone",
            headers={
                "Content-Type": "application/json",
                "Authorization": "5f2acde3-9ffb-46c7-ac07-ab4628e52146",  # Replace with your actual API key
            },
            json={
                "phoneNumberId": "417409c8-9a0e-4d2e-87ed-c9665557832c",
                "assistantId": "df71a9ab-c83c-4497-adbd-6fb95f01f8eb",
                "customer": {
                    "number": "+12403540561",  # Replace with the actual phone number
                },
            },
        )

        response.raise_for_status()
        return jsonify(response.json()), 200  # Send the response data as JSON
    except requests.exceptions.RequestException as error:
        return jsonify(
            {
                "message": "Failed to place outbound call",
                "error": str(error),
            }
        ), 500  # Handle errors
        
        
@api_blueprint.route('/on_call_end', methods=['POST']) 
def on_call_end():
    try:
        data = request.get_json()
        data = data.get("message").get("toolCalls")[0].get("function").get("arguments")
        call_id = data.get("call_id")
        site_rating = data.get("site_feedback")
        agent_rating = data.get("agent_feedback")

        if not call_id:
            return jsonify({"error": "Missing call_id"}), 400
        
        if not site_rating:
            return jsonify({"error": "Missing site_rating"}), 400
        
        if not agent_rating:
            return jsonify({"error": "Missing agent_rating"}), 400
        
        print("Received call end event:", data)
        return jsonify({"message": "Call end event received"}), 200

        # # Fetch call details from VAPI
        # response = requests.get(
        #     f"https://api.vapi.ai/call/{call_id}",
        #     headers={"Authorization": "Bearer YOUR_VAPI_API_KEY"}
        # )
        # if response.status_code != 200:
        #     return jsonify({"error": "Failed to fetch VAPI data"}), 502

        # call_data = response.json()

        # # Extract fields
        # call_type = call_data.get("type")
        # user_phone = call_data.get("customer", {}).get("number")
        # summary = call_data.get("analysis", {}).get("summary")
        # recording_url = call_data.get("recordingUrl")
        # stereo_recording_url = call_data.get("stereoRecordingUrl")
        # call_time = call_data.get("createdAt")
        # duration = call_data.get("duration")
        # messages = json.dumps(call_data.get("messages", []), indent=2)

        # # Convert time
        # call_time = datetime.fromisoformat(call_time.replace("Z", "+00:00"))

        # conn = get_connection()
        # cursor = conn.cursor()

        # # Check if already exists
        # cursor.execute("SELECT 1 FROM call_logs WHERE call_id = ?", (call_id,))
        # if cursor.fetchone():
        #     return jsonify({"message": "Call already logged"}), 200

        # # Insert log
        # cursor.execute("""
        #     INSERT INTO call_logs (
        #         call_id, type, user_phone, site_rating, agent_rating,
        #         summary, recording_url, stereo_recording_url,
        #         call_time, call_duration, messages
        #     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        # """, (
        #     call_id, call_type, user_phone, site_rating, agent_rating,
        #     summary, recording_url, stereo_recording_url,
        #     call_time, duration, messages
        # ))

        # conn.commit()
        # return jsonify({"message": "Call log recorded"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500