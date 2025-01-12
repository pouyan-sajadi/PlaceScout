# PlaceScout

Welcome to PlaceScout, an intelligent application crafted to enhance the discovery of places and navigation using advanced natural language processing. This project harnesses the capabilities of OpenAI's language models and the Google Maps API to deliver a seamless and intuitive experience for users seeking to explore and navigate the world around them.

## Project Overview
PlaceScout is a testament to the integration of machine learning engineering, data science, and software development. It showcases the application of cutting-edge technologies in natural language processing, API integration, and user interface design to solve real-world problems.

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
4. 
OPENAI_API_KEY=your_openai_key

GOOGLE_MAPS_API_KEY=your_google_maps_key

OpenAI_model=gpt-4o-mini (or any other OpenAI model)

5. Run the app: `streamlit run interface.py`

## Usage
- Find Places: Type queries like "Find coffee shops near Stanley Park, Vancouver" to get a list of places with detailed information.
- Get Directions: Use queries like "Directions from Central Park to Times Square" to receive step-by-step navigation.
- Explore Recent Places: Access your recent searches from the sidebar for quick reference.

## Deploy
The app is configured for deployment on Streamlit Cloud.
