import streamlit as st
from backend import parse_prompt, find_places, get_directions, handle_general_query, summarize_places, calculate_remaining_open_time
import json
import re

def initialize_session_state():
    """Initialize session state variables"""
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []
    if 'places_history' not in st.session_state:
        st.session_state.places_history = {}
    if 'place_address_map' not in st.session_state:
        st.session_state.place_address_map = {}

def get_place_photo(photo_reference, max_width=400):
    """Get place photo using photo reference"""
    if not photo_reference:
        return None
    
    try:
        from backend import gmaps  # Import the Google Maps client from main.py
        
        photo = gmaps.places_photo(
            photo_reference=photo_reference,
            max_width=max_width
        )
        
        if photo:
            # Convert the generator to bytes
            from io import BytesIO
            photo_bytes = BytesIO()
            for chunk in photo:
                photo_bytes.write(chunk)
            
            return photo_bytes.getvalue()
            
    except Exception as e:
        st.error(f"Error getting photo: {str(e)}")
        return None
    
def clear_chat():
    """Clear all session state data"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.conversation = []
    st.session_state.places_history = {}
    st.session_state.place_address_map = {}

def display_message(role, content):
    """Display a message in the chat interface"""
    with st.chat_message(role):
        st.markdown(content)

def main():
    
    st.set_page_config(
        page_title="AI Place Finder",
        page_icon="🗺️",
        layout="wide"
    )

    # Initialize session state
    initialize_session_state()

    # Main chat interface
    st.title("Chat with AI Place Finder 🗺️")

    # Display conversation history
    for message in st.session_state.conversation:
        display_message(
            message["role"],
            message["content"]
        )

    # Chat input
    if prompt := st.chat_input("What would you like to know?"):
        # Display user message
        display_message("user", prompt)
        st.session_state.conversation.append({"role": "user", "content": prompt})

        # Parse user input
        parsed_input = parse_prompt(prompt, st.session_state.conversation)
        
        try:
            if parsed_input:
                action = parsed_input.get('action')
                parameters = parsed_input.get('parameters', {})

                if action == 'find_places':
                    location = parameters.get('location')
                    place_type = parameters.get('place_type', 'restaurant')

                    if location == "None":
                        response = "Please provide a location."
                        display_message("assistant", response)
                        st.session_state.conversation.append({"role": "assistant", "content": response})
                    else:
                        places = find_places(location, place_type)
                        if not places:
                            response = f"No {place_type}s found near {location}."
                            display_message("assistant", response)
                            st.session_state.conversation.append({"role": "assistant", "content": response})
                        else:
                            # Get summarized response
                            summary = summarize_places(places, place_type, st.session_state.conversation)
                            
                            # Store places and their addresses in session state
                            for place in summary['places']:
                                place_name = place['place_name'].lower()
                                if 'address' in place:  # Store address if available
                                    st.session_state.place_address_map[place_name] = place['address']
                            
                            # Display results in chat
                            with st.chat_message("assistant"):
                                st.markdown(f"### 📍 Found places near {location}\n")
                                
                                for place, p in zip(places, summary['places']):
                                    st.markdown(f"## 🏢 {place['name']}")
                                    
                                    details = f"""
📍 **Address:** {place.get('formatted_address', 'Address not available')}

⭐ **Rating:** {place.get('rating', 'No rating')} ({place.get('user_ratings_total', 0)} reviews)

💰 **Price Level:** {place.get('price_level', 'Not specified')}

⏰ **Remaining Opening Time:** {calculate_remaining_open_time(place)}

🎯 **Our Take:** {p['assistant_take']}

👥 **Summary of Recent Reviews:** {p['review_summary']}
"""
                                    st.markdown(details)
                                    
                                    # Display photo
                                    try:
                                        photo_reference = place['photos'][0]['photo_reference']
                                        photo_bytes = get_place_photo(photo_reference)
                                        if photo_bytes:
                                            st.image(photo_bytes, width=400)
                                    except Exception as e:
                                        with st.sidebar:
                                            st.error(f"Photo error: {str(e)}")
                                    
                                    st.markdown("---")
                                
                                st.markdown(f"**Overall Summary:**\n{summary['overall_summary']}")

                            # Store places with more details
                            for place in places:
                                place_name = place['name'].lower()
                                st.session_state.places_history[place_name] = {
                                    'address': place.get('formatted_address'),
                                    'rating': place.get('rating', 'No rating'),
                                    'total_ratings': place.get('user_ratings_total', '0'),
                                }
                                # Also store in address map for directions functionality
                                st.session_state.place_address_map[place_name] = place.get('formatted_address')

                            # Store a simplified version in conversation history
                            response = f"Found places near {location}. See details above."
                            st.session_state.conversation.append({"role": "assistant", "content": response})

                elif action == 'get_directions':
                    destination = parameters.get('destination', '').lower()
                    origin = parameters.get('origin')
                    mode = parameters.get('mode', 'driving')

                    if not destination:
                        response = "Please provide a destination."
                    elif not origin:
                        response = "Please provide a starting location."
                    else:
                        try:
                            # Check if destination is in our stored places
                            if destination in st.session_state.place_address_map:
                                destination = st.session_state.place_address_map[destination]
                                with st.sidebar:
                                    st.write("Using stored address:", destination)

                            directions = get_directions(origin, destination, mode)
                            
                            if directions and isinstance(directions, dict):
                                response = f"### 🚗 Directions from {origin} to {destination}\n\n"
                                response += f"**Distance:** {directions['distance']}\n"
                                response += f"**Duration:** {directions['duration']}\n\n"
                                response += "**Steps:**\n"
                                
                                for i, step in enumerate(directions['steps'], 1):
                                    clean_step = re.sub('<[^<]+?>', '', step)
                                    response += f"{i}. {clean_step}\n"
                            else:
                                response = f"Sorry, I couldn't find directions from {origin} to {destination}."
                        except Exception as e:
                            response = "Error getting directions: Please make sure both locations are valid."
                            with st.sidebar:
                                st.error(f"Error: {str(e)}")

                else:  # chat action
                    response = handle_general_query(prompt, st.session_state.conversation)

            else:
                response = "I'm sorry, I couldn't understand your request. Could you please rephrase it?"

            # Display assistant response
            display_message("assistant", response)
            st.session_state.conversation.append({"role": "assistant", "content": response})

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            display_message("assistant", error_message)
            st.session_state.conversation.append({"role": "assistant", "content": error_message})

    # Sidebar
    with st.sidebar:
        st.title("🗺️ AI Place Finder")
        
        # Welcome section with collapsible instructions
        with st.expander("ℹ️ How to use", expanded=False):
            st.markdown("""
            ### Welcome! 👋
            I can help you:
            
            🔍 **Find Places**
            - *"Find pizza places near Central Park"*
            - *"Show me coffee shops in downtown"*
            
            🗺️ **Get Directions**
            - *"How do I get to Times Square?"*
            - *"Directions from A to B"*
            
            💡 **Tips:**
            1. Search for places first
            2. Then get directions using exact place names
            """)
           
        # Recent Places section
        st.markdown("### 📍 Recent Places")
        
        if st.session_state.places_history and len(st.session_state.places_history) > 0:
            for place_name, details in st.session_state.places_history.items():
                with st.expander(f"🏢 {place_name.title()}", expanded=False):
                    if details:  # Check if details exist
                        st.markdown(f"⭐ **Rating:** {details.get('rating', 'No rating')} ({details.get('total_ratings', '0')} reviews)")
                        st.markdown(f"📍 **Address:** {details.get('address', 'Address not available')}")
                    else:
                        st.markdown("Details not available")
        else:
            st.markdown("*No places found yet. Try searching for some!*")

        # Clear chat button
        if st.button("🗑️ Clear Chat", key="clear_chat_button"):
            clear_chat()
            st.rerun()            

if __name__ == "__main__":
    main()