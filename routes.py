from flask import Blueprint, request, jsonify, render_template, Flask
from database import get_connection
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import logging
import json
import requests
from pydantic import BaseModel, ValidationError
from typing import List, Dict, Union
from config import API_KEY, GEMINI_API_KEY
from datetime import datetime
import google.generativeai as genai

api_blueprint = Blueprint("api", __name__)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


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

def get_lat_lon_by_address(address):
    if address:
        try:
            resp = requests.get(f"https://api.zippopotam.us/us/{address}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                place = data["places"][0]
                lat = float(place["latitude"])
                lng = float(place["longitude"])
                user_coords = (lat, lng)
                return user_coords
            else:
                return jsonify({"error": "Location not found"}), 404
        except requests.RequestException:
            return jsonify({"error": "Geocoding service unavailable"}), 503
    elif lat and lng: # If user gave the site their current location
        user_coords = (float(lat), float(lng))  
        return user_coords
    else:
        return jsonify({"error": "Address or coordinates are required"}), 400

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


def fetch_filtered_agencies(address, day_of_week, max_distance=5.0):
    try:
        user_lat, user_lon = get_lat_lon(address)
        if not user_lat or not user_lon:
            return {"error": "Invalid location"}, 400

        conn = get_connection()
        cursor = conn.cursor()

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

        result = []
        for agency in agency_map.values():
            agency["wraparound_services"] = list(agency["wraparound_services"])
            agency["cultures_served"] = list(agency["cultures_served"])
            result.append(agency)

        result.sort(key=lambda x: x["distance"])
        conn.close()
        return result, 200

    except Exception as e:
        logging.error(f"Expert Query Error: {e}")
        return {"error": str(e)}, 500

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
    
   
    user_coords = get_lat_lon_by_address(address)
    conn = get_connection()
    cursor = conn.cursor()

    # This query retrieves all necessary agency data with joins
    agencies = cursor.execute("""SELECT a.agency_id, a.name, a.type, a.address, a.phone, a.latitude, a.longitude,
                   h.day_of_week, h.start_time, h.end_time ,h.distribution_model, h.food_format, h.appointment_only, h.pantry_requirements,
                   w.service, c.cultures, a.updates, a.last_update_time
            FROM agencies a
            JOIN hours_of_operation h ON a.agency_id = h.agency_id
            LEFT JOIN wraparound_services w ON a.agency_id = w.agency_id
            LEFT JOIN cultures_served c ON a.agency_id = c.agency_id""")
    conn.close()
    
    nearby_agencies = []
    

    for agency in agencies:
        agency_id, name, type, address, phone, latitude, longitude, day_of_week, start_time, end_time, distribution, food_format, appointment, pantry_req, wrap_service, culture, updates, last_update_time = agency  # unpack tuple
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
                "hours": open_hours,
                "updates": updates, 
                "last_update_time": last_update_time,
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
                    "hours": open_hours,
                    "updates": updates, 
                    "last_update_time": last_update_time,
                })
            
        
    
    return jsonify(nearby_agencies)

# ----------------------------
# Expert Query Route (Browser)
# ----------------------------

@api_blueprint.route("/expertquery", methods=["GET"])
def get_filtered_agencies():
    address = request.args.get("address")
    day_of_week = request.args.get("day_of_week")
    max_distance = float(request.args.get("max_distance", 5.0))
    
    agencies, status_code = fetch_filtered_agencies(address, day_of_week, max_distance)
    
    if status_code != 200:
        return jsonify(agencies), status_code
        
    return jsonify(agencies), 200


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
        payload = request.get_json(force=True)
        data = VapiRequest(**payload)

        for tool_call in data.message.toolCalls:
            if tool_call.function.name == "getFoodDistributionSites":
                args = tool_call.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)

                address = args["address"]
                day_of_week = args["day_of_week"]

                # Call the new function directly with the parsed arguments
                response_data, status_code = fetch_filtered_agencies(address, day_of_week)

                if status_code != 200:
                    return jsonify({"results": [{"toolCallId": tool_call.id, "result": json.dumps(response_data)}]}), status_code

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

# ----------------------------
# Donation Chat Route
# ----------------------------

# @api_blueprint.route("/donate/chat", methods=["POST"])
# def donate_chat():
#     try:
#         data = request.get_json()
#         user_message = data.get("message", "").strip()
#         chat_history = data.get("history", [])
        
#         if not user_message:
#             return jsonify({"error": "Message is required"}), 400
                
#         # Create conversation context
#         conversation_context = """
#         You are a helpful assistant for a food donation platform. Your role is to:
#         1. Help users specify what they want to donate
#         2. Ask for their zip code to find nearby food providers
#         3. Guide them through the donation process
        
#         Keep responses concise and friendly. Always ask for zip code after the user specifies what they want to donate.
#         """
        
#         # Build conversation history for context
#         full_conversation = conversation_context + "\n\n"
#         for msg in chat_history:
#             role = "User" if msg.get("role") == "user" else "Assistant"
#             full_conversation += f"{role}: {msg.get('content', '')}\n"
        
#         full_conversation += f"User: {user_message}\nAssistant:"
        
#         # Get response from Gemini
#         try:
#             response = model.generate_content(full_conversation)
#             ai_response = response.text.strip()
#         except Exception as e:
#             logging.error(f"Gemini API error: {e}")
#             return jsonify({"error": f"AI service error: {str(e)}"}), 500
        
#         # Check if user provided donation details and we need zip code
#         needs_zip = False
#         extracted_food_item = None
        
#         # if any(keyword in user_message.lower() for keyword in ['donate', 'give', 'have', 'want to donate']):
#         if not any(msg.get('content', '').lower().find('zip') != -1 for msg in chat_history):
#             needs_zip = True
#             ai_response = f"Great! To help you find the best place to donate, please provide your zip code so I can show you nearby food providers."
#                 # Extract food item using AI
#                 # extracted_food_item = donation_service.extract_food_item(user_message)
#                 # ai_response = f"Great! I see you want to donate {extracted_food_item}. To help you find the best place to donate, please provide your zip code so I can show you nearby food providers."
        
#         return jsonify({
#             "response": ai_response,
#             "needs_zip": needs_zip,
#             "extracted_food_item": extracted_food_item,
#             "status": "success"
#         }), 200
        
#     except Exception as e:
#         logging.error(f"Chat error: {e}")
#         return jsonify({"error": "Failed to process chat message"}), 500

# # ----------------------------
# # Get Agencies by Zip Code
# # ----------------------------

# @api_blueprint.route("/donate/agencies", methods=["GET"])
# def get_agencies_by_zip():
#     try:
#         zip_code = request.args.get("zip_code")
#         if not zip_code:
#             return jsonify({"error": "Zip code is required"}), 400
        
#         # result = donation_service.get_agencies_by_zip(zip_code)
        
#         if "error" in result:
#             return jsonify(result), 400
        
#         return jsonify(result), 200
        
#     except Exception as e:
#         logging.error(f"Get agencies error: {e}")
#         return jsonify({"error": "Failed to get agencies"}), 500

# # ----------------------------
# # Update Donation
# # ----------------------------

# @api_blueprint.route("/donate/update", methods=["POST"])
# def update_donation():
#     try:
#         data = request.get_json()
#         agency_id = data.get("agency_id")
#         donation_item = data.get("donation_item")
        
#         if not agency_id or not donation_item:
#             return jsonify({"error": "Agency ID and donation item are required"}), 400
        
#         # donation_service = DonationService()
#         # result = donation_service.update_donation(agency_id, donation_item)
        
#         if "error" in result:
#             return jsonify(result), 400
        
#         return jsonify(result), 200
        
#     except Exception as e:
#         logging.error(f"Update donation error: {e}")
#         return jsonify({"error": "Failed to update donation"}), 500

# # ----------------------------
# # Clear Old Updates (for maintenance)
# # ----------------------------

# @api_blueprint.route("/donate/clear-old-updates", methods=["POST"])
# def clear_old_updates():
#     try:
#         # donation_service = DonationService()
#         # success = donation_service.clear_old_updates()
        
#         if success:
#             return jsonify({"message": "Old updates cleared successfully"}), 200
#         else:
#             return jsonify({"error": "Failed to clear old updates"}), 500
            
#     except Exception as e:
#         logging.error(f"Clear old updates error: {e}")
#         return jsonify({"error": "Failed to clear old updates"}), 500

@api_blueprint.route("/donate/chat", methods=["POST"])
def donate_chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        chat_history = data.get("history", [])
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Use Gemini to extract food items and zip code
        extraction_prompt = f"""
        You are a food donation assistant. Extract the following information from the user message:

        REQUIRED FORMAT: Return ONLY valid JSON with this exact structure:
        {{
            "food_items": ["item1", "item2", ...],
            "zip_code": "12345" or null
        }}

        INSTRUCTIONS:
        - Extract all food items mentioned (canned goods, fresh produce, dairy, etc.)
        - Extract any 5-digit US zip code
        - If no food items found, use empty array: []
        - If no zip code found, use null
        - Return ONLY the JSON, no additional text

        USER MESSAGE: "{user_message}"

        JSON RESPONSE:
        """
        
        try:
            # Extract information using Gemini
            extraction_response = model.generate_content(extraction_prompt)
            response_text = extraction_response.text.strip()
            
            # Clean up the response to extract JSON
            # Remove any markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            # Parse the JSON response
            extracted_data = json.loads(response_text)
            
            food_items = extracted_data.get("food_items", [])
            zip_code = extracted_data.get("zip_code")
            
            # Validate zip code format if present
            if zip_code and (not isinstance(zip_code, str) or not zip_code.isdigit() or len(zip_code) != 5):
                zip_code = None
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {e}, Response: {response_text}")
            food_items = []
            zip_code = None
        except Exception as e:
            logging.error(f"Gemini extraction error: {e}")
            food_items = []
            zip_code = None
        
        # Generate conversational response
        conversation_context = """
        You are a helpful assistant for a food donation platform. Your role is to:
        1. Help users specify what they want to donate
        2. Ask for their zip code to find nearby food providers
        3. Guide them through the donation process
        
        Keep responses concise and friendly. If the user mentions food items but no zip code, ask for zip code.
        """
        
        # Build conversation history for context
        messages = [{"role": "user", "parts": [conversation_context]}]
        
        for msg in chat_history:
            role = "user" if msg.get("role") == "user" else "model"
            messages.append({"role": role, "parts": [msg.get("content", "")]})
        
        messages.append({"role": "user", "parts": [user_message]})
        
        # Get conversational response
        try:
            chat = model.start_chat(history=messages)
            response = chat.send_message("Provide a helpful response about food donation")
            ai_response = response.text.strip()
        except Exception as e:
            logging.error(f"Gemini chat error: {e}")
            ai_response = "I'd be happy to help you find places to donate food. What would you like to donate?"
        
        # Determine if we need zip code
        needs_zip = False
        if food_items and not zip_code:
            needs_zip = True
            # Enhance the response to specifically ask for zip code
            if "zip" not in ai_response.lower() and "postal" not in ai_response.lower() and "location" not in ai_response.lower():
                food_list = ", ".join(food_items[:3])  # Show first 3 items
                if len(food_items) > 3:
                    food_list += f" and {len(food_items) - 3} more items"
                ai_response = f"Great! I see you want to donate {food_list}. To find nearby donation centers, please provide your 5-digit zip code."
        
        return jsonify({
            "response": ai_response,
            "needs_zip": needs_zip,
            "extracted_food_items": food_items,
            "extracted_zip_code": zip_code,
            "status": "success"
        }), 200
        
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return jsonify({"error": "Failed to process chat message"}), 500

@api_blueprint.route("/donate/agencies", methods=["GET"])
def get_agencies_by_zip():
    try:
        zip_code = request.args.get("zip_code")
        print(zip_code,food_items)
        if not zip_code:
            return jsonify({"error": "Zip code is required"}), 400
        
        # result = donation_service.get_agencies_by_zip(zip_code)
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Get agencies error: {e}")
        return jsonify({"error": "Failed to get agencies"}), 500