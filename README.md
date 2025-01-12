# PlaceScout

Welcome to PlaceScout, an intelligent application designed to help you discover places and get directions using natural language processing. This project leverages the power of OpenAI's language models and Google Maps API to provide a seamless experience for finding and navigating to places.

## Features

- **Natural Language Queries**: Ask questions like "Find sushi restaurants near me" or "How do I get to the nearest gas station?" and get instant results.
- **Detailed Place Information**: View comprehensive details about places, including addresses, ratings, reviews, price levels, and photos.
- **Directions**: Get step-by-step directions from one location to another, with support for different travel modes (driving, walking, bicycling, transit).
- **Recent Searches**: Keep track of your recent searches and easily revisit places.
- **Interactive Map**: Visualize places on a map for better spatial understanding (optional feature).

## Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your API keys:
OPENAI_API_KEY=your_openai_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
OpenAI_model=gpt-4-mini (or any other OpenAI model)

4. Run the app: `streamlit run interfave.py`

## Usage
- Find Places: Type queries like "Find coffee shops in New York" to get a list of places with detailed information.
- Get Directions: Use queries like "Directions from Central Park to Times Square" to receive step-by-step navigation.
- Explore Recent Places: Access your recent searches from the sidebar for quick reference.

## Deploy
The app is configured for deployment on Streamlit Cloud.
