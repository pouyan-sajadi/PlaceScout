import os
from dotenv import load_dotenv
from openai import OpenAI
import googlemaps
import json
from datetime import datetime
import re
from categories import PLACE_CATEGORIES
import streamlit as st

# Load environment variables for local development
load_dotenv()

# Initialize API keys - prioritize Streamlit secrets over environment variables
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
except Exception:
    # Fallback to environment variables for local development
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

# Initialize clients with error handling
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
except Exception as e:
    st.error(f"Error initializing API clients: {str(e)}")
    st.error("Please ensure API keys are properly configured in Streamlit secrets or environment variables.")

# Global variables
OpenAI_model = "gpt-4o-mini"
conversation_history = []
place_address_map = {}  # Store place names and their formatted addresses

def parse_prompt(user_input, conversation_history=[]):
    """
    Uses OpenAI's API to parse the user's prompt and extract the required action and parameters.
    Includes conversation context for better understanding but focuses on parsing the last input.
    """
    # Prepare conversation context
    conversation_text = "\n".join([
        f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
        for msg in conversation_history[-5:]  # Get last 5 messages for context
    ])

    system_message = f"""
You are a helpful assistant that can:

1. Find places ('find_places' action):
   - Help users find places of a specific type near a location based their last message
   - Do NOT include additional place types unless specifically requested
   - Requires parameters: "location" and "place_type". 

2. Get directions ('get_directions' action):
   - Provide directions from one location to another
   - When users refer to previously mentioned places, find and use their full addresses in the places list in the chat history
   - If destination matches any recently mentioned place names, use their full address found in the place's list the chat history


3. Answer general queries ('chat' action):
   - If the user's input doesn't match the above actions, respond as a knowledgeable assistant
   - This should be your default mode.
   - For these queries, set action as "chat" and include the user's query in parameters as "query"

Below is the recent conversation context, followed by the latest user message that needs to be parsed.
While you can use the context to better understand the user's intent, please parse ONLY the last message
to determine the action and parameters.

Recent Conversation:
{conversation_text}

Latest message to parse: "{user_input}"

Respond in JSON format with one of these structures:

For finding places:
{{
    "action": "find_places",
    "parameters": {{
        "location": "specified location (if no place is specified put None)",
        "place_type": "type of place"
    }}
}}

For getting directions:
{{
    "action": "get_directions",
    "parameters": {{
        "origin": "starting point (should be a full address found on chat history)",
        "destination": "ending point (should be a full address found on chat history)",
        "mode": "driving|walking|bicycling|transit (optional)"
    }}
}}

For general chat:
{{
    "action": "chat",
    "parameters": {{
        "query": "original user query"
    }}
}}
"""

    response = client.chat.completions.create(
        model=OpenAI_model,
        messages=[
            {
                "role": "system",
                "content": system_message
            }
        ],
        max_tokens=150,
        temperature=0.0
    )

    try:
        result = json.loads(response.choices[0].message.content.strip())
        return result
    except json.JSONDecodeError:
        return None

def identify_primary_category(user_input, conversation_history=[]):
    """
    Use LLM to identify the primary category from user input.
    Returns the most appropriate category from PLACE_CATEGORIES keys.
    """
    categories_list = list(PLACE_CATEGORIES.keys())
    
    prompt = f"""
Given a user's request, identify the most appropriate primary category from the following list:
{', '.join(categories_list)}

User's input: "{user_input}"
Recent conversation context:
{chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]])}

Rules:
1. Choose ONLY ONE category from the provided list
2. If multiple categories might apply, choose the most specific/relevant one
3. If no category seems to match, return "unknown"

Respond with just the category name, nothing else.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise categorization assistant that matches user requests to predefined categories."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=50
        )

        category = response.choices[0].message.content.strip().lower()
        return category 
    
    except Exception as e:
        print(f"Error in category identification: {str(e)}")
        return "restaurant"

def identify_subcategory(primary_category, user_input, conversation_history=[]):
    """
    Use LLM to identify the specific subcategory within the primary category.
    Returns the most relevant keyword for the Places API call.
    """
    if primary_category.lower() not in (key.lower() for key in PLACE_CATEGORIES):
        return None, None

    subcategories = PLACE_CATEGORIES[primary_category]

    prompt = f"""
For a {primary_category} search, identify the most specific subcategory or keyword from the following options:
{', '.join(subcategories)}

User's input: "{user_input}"
Recent conversation context:
{chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]])}

Rules:
1. Choose the most specific subcategory that matches the user's request
2. You can suggest up to 2 relevant subcategories if the request is ambiguous
3. If no subcategory matches well, respond with "general"

Respond in this exact format:
primary: [primary_subcategory]
secondary: [secondary_subcategory or "none"]
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a specialized {primary_category} categorization assistant that matches user requests to specific subcategories."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=50
        )

        # Parse the response
        response_text = response.choices[0].message.content.strip()
        response_lines = response_text.split('\n')
        primary_sub = response_lines[0].split(': ')[1].strip()
        secondary_sub = response_lines[1].split(': ')[1].strip()
        
        if secondary_sub.lower() == 'none':
            secondary_sub = None
            
        return primary_sub, secondary_sub
    
    except Exception as e:
        print(f"Error in subcategory identification: {str(e)}")
        return "general", None

def clean_json_response(response_text):
    """Clean the response text by removing markdown formatting"""
    # Remove ```json and ``` markers
    cleaned = response_text.replace('```json', '').replace('```', '').strip()
    return cleaned

def find_places(location, user_input, conversation_history=[]):
    """
    Find places based on user input, using category identification and Google Maps API.
    
    Args:
        location (str): Location to search near
        user_input (str): User's original request
        conversation_history (list): List of previous conversation messages
    
    Returns:
        list: List of place details
    """
    # First, identify the primary category
    primary_category = identify_primary_category(user_input, conversation_history)
    
    # Then, identify the subcategory
    primary_sub, secondary_sub = identify_subcategory(
        primary_category, user_input, conversation_history
    )
    
    # Geocode the location
    geocode_result = gmaps.geocode(location)
    if not geocode_result:
        return None

    latlng = geocode_result[0]['geometry']['location']
    
    # Search for places using both type and keyword
    places_result = gmaps.places_nearby(
        location=(latlng['lat'], latlng['lng']),
        radius=1500,
        type=primary_category,
        keyword=primary_sub if primary_sub != "general" else None
    )
    
    # If no results with primary subcategory, try secondary
    if not places_result.get('results') and secondary_sub:
        places_result = gmaps.places_nearby(
            location=(latlng['lat'], latlng['lng']),
            radius=1500,
            type=primary_category,
            keyword=secondary_sub
        )
    
    # If still no results, try without keyword
    if not places_result.get('results'):
        places_result = gmaps.places_nearby(
            location=(latlng['lat'], latlng['lng']),
            radius=1500,
            type=primary_category
        )

    if not places_result.get('results'):
        return None

    # Get detailed information for each place
    detailed_places = []
    for place in places_result['results'][:5]:  # Limit to top 5 places
        try:
            place_details = gmaps.place(
                place['place_id'],
                fields=[
                    'name',
                    'formatted_address',
                    'rating',
                    'reviews',
                    'current_opening_hours',
                    'user_ratings_total',
                    'price_level',
                    'formatted_phone_number',
                    'website',
                    'editorial_summary',
                    'business_status',
                    'geometry',
                    'photo'
                ]
            )
            
            if place_details.get('status') == 'OK':
                result = place_details['result']
                # Add the types from the nearby search to the place details
                result['types'] = place.get('types', [])
                # Add the subcategory information for context
                result['searched_category'] = primary_category
                result['searched_subcategory'] = primary_sub if primary_sub != "general" else None
                detailed_places.append(result)
                
        except Exception as e:
            print(f"Error getting details for place: {str(e)}")
            continue

    return detailed_places

def summarize_reviews(reviews):
    """
    Uses OpenAI's API to generate a summary of place reviews.
    """
    if not reviews:
        return "No reviews available."

    reviews_text = "\n".join([review['text'] for review in reviews[:5]])
    
    response = client.chat.completions.create(
        model=OpenAI_model,
        messages=[
            {"role": "system", "content": "Summarize the key points from these reviews concisely:"},
            {"role": "user", "content": reviews_text}
        ],
        max_tokens=100,
        temperature=0.0
    )
    
    return response.choices[0].message.content.strip()

def calculate_remaining_open_time(place):
    """
    Calculates how much longer a place will remain open.
    """
    if not place.get('current_opening_hours', {}).get('periods'):
        return "Hours not available"

    now = datetime.now()
    current_time = now.hour * 60 + now.minute  # Convert to minutes

    for period in place['current_opening_hours']['periods']:
        if 'close' in period:
            close_time = period['close']['time']
            close_hour = int(close_time[:2])
            close_minute = int(close_time[2:])
            close_in_minutes = close_hour * 60 + close_minute

            if close_in_minutes > current_time:
                remaining_minutes = close_in_minutes - current_time
                hours = remaining_minutes // 60
                minutes = remaining_minutes % 60
                return f"Open for {hours} hours and {minutes} minutes"

    return "Currently closed"

def get_directions(origin, destination, mode='driving'):
    """
    Get directions between two locations.
    """
    try:
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            mode=mode,
            departure_time=datetime.now()
        )

        if not directions_result:
            return None

        route = directions_result[0]['legs'][0]
        return {
            'distance': route['distance']['text'],
            'duration': route['duration']['text'],
            'steps': [step['html_instructions'] for step in route['steps']]
        }
    except Exception as e:
        print(f"Error getting directions: {e}")
        return None

def summarize_places(places, place_type, conversation_history):
    """
    Summarize all places in a single LLM call and return structured data
    """
    places_info = []
    for place in places:
        place_info = {
            'name': place.get('name', 'Unknown'),
            'address': place.get('formatted_address', 'Address not available'),
            'rating': place.get('rating', 'No rating'),
            'total_ratings': place.get('user_ratings_total', 0),
            'reviews': place.get('reviews', [])[:2],
            'opening_hours': calculate_remaining_open_time(place),
            'types': place.get('types', []),
            'price_level': place.get('price_level', 'Not specified')
        }
        places_info.append(place_info)

    places_details = ""
    for place in places_info:
        places_details += f"""
Place: {place['name']}
- Type: {', '.join(place['types'])}
- Rating: {place['rating']} ({place['total_ratings']} reviews)
- Price Level: {place['price_level']}
- Address: {place['address']}
- Current Status: {place['opening_hours']}
- Reviews:
{chr(10).join([f"  - {review.get('text', '')}" for review in place['reviews']])}
"""

    prompt = f"""
You are analyzing {place_type}s. Respond with ONLY a JSON object in the following format, without any markdown formatting or additional text:

{{
    "places": [
        {{
            "place_name": "exact name of the place",
            "address": "full address of the place"
            "assistant_take": "2-3 sentences highlighting key features, atmosphere, and standout qualities",
            "review_summary": "1-2 sentences summarizing customer reviews and ratings"
        }}
    ],
    "overall_summary": "2 sentences comparing these places and highlighting the best options"
}}

Here are the places to analyze:

{places_details}

IMPORTANT:
1. Do NOT include markdown formatting (no ```json or ```)
2. Respond ONLY with the JSON object
3. Ensure valid JSON structure
4. Include all places in the response
"""

    try:
        response = client.chat.completions.create(
            model=OpenAI_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON-focused assistant that responds only with raw JSON, no markdown formatting."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.1
        )

        # Clean and parse the response
        raw_response = response.choices[0].message.content.strip()
        cleaned_response = clean_json_response(raw_response)
        
        # Print cleaned response for debugging
        #print("\nCleaned Response:", cleaned_response)
        
        # Parse JSON response
        summary_dict = json.loads(cleaned_response)
        return summary_dict

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        print("Raw content:", raw_response)
        print("Cleaned content:", cleaned_response)
        return {
            "places": [{"place_name": place["name"], 
                       "address": "Address not avialable",                      
                       "assistant_take": "Information not available", 
                       "review_summary": "Reviews not available"} 
                      for place in places_info],
            "overall_summary": f"Found {len(places_info)} {place_type}s."
        }
    except Exception as e:
        print(f"Other error: {str(e)}")
        return {
            "places": [{"place_name": place["name"], 
                       "address": "Address not avialable",
                       "assistant_take": "Information not available", 
                       "review_summary": "Reviews not available"} 
                      for place in places_info],
            "overall_summary": f"Found {len(places_info)} {place_type}s."
        }

def handle_general_query(query, conversation_history):
    """
    Handle general knowledge queries using the LLM.
    Prints the response and updates conversation history.
    
    Args:
        query (str): The user's query
        conversation_history (list): List of conversation dictionaries
    """
    # Prepare messages for the chat
    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant that provides informative 
            and concise responses. If the query is about locations, travel, or places, 
            remind the user that you can help them find specific places or get directions 
            using commands like 'find places near...' or 'get directions to...'
            
            Consider the conversation history when providing responses to maintain context 
            and give relevant answers.
            
            If the user asks about specific locations or places, encourage them to use
            the proper commands to get detailed information and accurate results."""
        }
    ]

    # Add recent conversation history for context
    messages.extend(conversation_history[-5:])  # Include last 5 messages
    
    # Add the current query
    messages.append({"role": "user", "content": query})

    # Get response from OpenAI
    response = client.chat.completions.create(
        model=OpenAI_model,
        messages=messages,
        max_tokens=150,
        temperature=0.1
    )
    
    # Extract and print the assistant's response
    assistant_response = response.choices[0].message.content.strip()

    return assistant_response  # Return response   

def main():
    # Move conversation_history to global scope or use st.session_state if using Streamlit
    global conversation_history
    if 'conversation_history' not in globals():
        conversation_history = []

    print("""
Welcome to your AI Map Assistant! 👋

I can help you:
🔍 Find places: "Find pizza places near Central Park"
🗺️ Get directions: "How do I get to Times Square by transit?"

Try asking me to find something near a location!
""")
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("Goodbye!")
            break

        # Add user input to history
        conversation_history.append({"role": "user", "content": user_input})

        # Parse input
        parsed_input = parse_prompt(user_input, conversation_history)
        if not parsed_input:
            handle_general_query(user_input, conversation_history)
            continue

        action = parsed_input.get('action')
        parameters = parsed_input.get('parameters', {})

        try:
            if action == 'find_places':
                location = parameters.get('location')
                place_type = parameters.get('place_type', 'restaurant')
                
                if location == "None":
                    print("Please provide a location.")
                    continue

                places = find_places(location, place_type)
                if not places:
                    print(f"No {place_type}s found near {location}.")
                    continue

                # Store addresses
                for place in places:
                    place_name = place.get('name', '').lower()
                    formatted_address = place.get('formatted_address')
                    if place_name and formatted_address:
                        place_address_map[place_name] = formatted_address

                # Get summarized response for all places
                response = summarize_places(places, place_type, conversation_history)
                summary_dict = response  # response is already a dictionary from the modified summarize_places function

                # Debug prints
                print("\nStructured Summary:")
                print(f"Overall Summary: {summary_dict['overall_summary']}")
                print("\nIndividual Place Summaries:")
                for place_summary in summary_dict['places']:
                    print(f"\nPlace: {place_summary['place_name']}")
                    print(f"\nAddress: {place_summary['address']}")                    
                    print(f"Assistant's Take: {place_summary['assistant_take']}")
                    print(f"Review Summary: {place_summary['review_summary']}")
                print("\n")

                # Add response to conversation history
                conversation_history.append({
                    "role": "assistant",
                    "content": response
                })
        # Handle get_directions action
            elif action == 'get_directions':
                destination = parameters.get('destination', '').lower()
                origin = parameters.get('origin')
                mode = parameters.get('mode', 'driving')
                if not destination:
                    print("Please provide a destination.")
                    continue

                if not origin:
                    origin = input("Please provide your starting location: ")

                # Get and display directions
                directions = get_directions(origin, destination, mode)
                if directions:
                    print(f"\nDistance: {directions['distance']}")
                    print(f"Duration: {directions['duration']}")
                    print("\nDirections:")
                    for i, step in enumerate(directions['steps'], 1):
                        # Clean HTML tags from steps
                        clean_step = re.sub('<[^<]+?>', '', step)
                        print(f"{i}. {clean_step}")
                else:
                    print("Sorry, I couldn't find directions.")

            # Then in your main function, replace the chat action handling with:
            elif action == 'chat':
                query = parameters.get('query')
                handle_general_query(query, conversation_history)

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            continue
if __name__ == "__main__":
    main()