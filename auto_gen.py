from flask import Flask, render_template, request, jsonify, g, send_from_directory
from flask_cors import CORS
from bs4 import BeautifulSoup
import requests
import spacy
import google.generativeai as genai
from collections import Counter
import os
import re
from dotenv import load_dotenv
import json
from datetime import datetime
import logging
import time
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {"origins": "*"},
    r"/generate_content": {"origins": "*"},
    r"/history": {"origins": "*"}
})

# Configuration class for app
class Config:
    API_KEY = os.getenv("API_KEY")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file size
    DATA_DIR = 'data'
    ALLOWED_DOMAINS = ['example.com', 'trusted-domain.com']  # Add trusted domains
    HISTORY_FILE = 'content_history.json'
    RATE_LIMIT_DELAY = 1  # 1 second delay between requests
    MAX_RETRIES = 3  # Maximum number of retries for API calls
    TIMEOUT = 30  # Timeout for external requests in seconds

# Initialize API and models
try:
    if not Config.API_KEY:
        raise ValueError("API_KEY environment variable not set!")
    genai.configure(api_key=Config.API_KEY)
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    logging.error(f"Initialization error: {e}")
    raise

# Ensure data directory exists
os.makedirs(Config.DATA_DIR, exist_ok=True)

# Custom Exceptions
class RateLimitExceededException(Exception):
    pass

class ContentFetchError(Exception):
    pass

class ProcessingError(Exception):
    pass

# Helper Functions
def read_history():
    try:
        if os.path.exists(Config.HISTORY_FILE):
            with open(Config.HISTORY_FILE, 'r') as file:
                return json.load(file)
        return []
    except Exception as e:
        logging.error(f"Error reading history: {e}")
        return []

def save_to_history(data):
    try:
        history = read_history()
        history.insert(0, {
            "url": data["url"],
            "keywords": data["keywords"],
            "generated_content": data["generated_content"],
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "word_count": len(data["generated_content"].split()),
                "keyword_count": len(data["keywords"])
            }
        })
        
        # Keep only the last 100 entries to manage file size
        history = history[:100]
        
        with open(Config.HISTORY_FILE, 'w') as file:
            json.dump(history, file, indent=4)
            
    except Exception as e:
        logging.error(f"Error saving to history: {e}")
        raise ProcessingError("Failed to save content history")

# Content Processing Classes
class WebScraper:
    @staticmethod
    def is_valid_url(url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def is_allowed_domain(url):
        try:
            domain = urlparse(url).netloc
            return domain in Config.ALLOWED_DOMAINS or True  # Remove 'or True' to enforce domain restrictions
        except Exception:
            return False

    @staticmethod
    def scrape_content(url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=Config.TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                element.decompose()

            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            
            if main_content:
                text = main_content.get_text()
                # Clean text
                text = re.sub(r'\s+', ' ', text).strip()
                text = re.sub(r'\n\s*\n', '\n', text)
                return text
            
            return None

        except requests.Timeout:
            raise ContentFetchError("Request timed out while fetching content")
        except requests.RequestException as e:
            raise ContentFetchError(f"Failed to fetch content: {str(e)}")

class ContentGenerator:
    @staticmethod
    def extract_keywords(text, num_keywords=10):
        try:
            # Limit text length for processing
            text = text[:50000]  
            doc = nlp(text)
            
            # Extract nouns and proper nouns
            keywords = [token.text.lower() for token in doc 
                       if token.pos_ in ["NOUN", "PROPN"] 
                       and len(token.text) > 2
                       and not token.is_stop]
            
            # Count frequency
            keyword_freq = Counter(keywords)
            
            # Get most common keywords
            most_common = keyword_freq.most_common(num_keywords)
            
            return [keyword for keyword, _ in most_common]
            
        except Exception as e:
            logging.error(f"Keyword extraction error: {e}")
            raise ProcessingError("Failed to extract keywords")

    @staticmethod
    def generate_content(prompt):
        retries = 0
        while retries < Config.MAX_RETRIES:
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                retries += 1
                if retries == Config.MAX_RETRIES:
                    logging.error(f"Content generation error after {retries} retries: {e}")
                    raise ProcessingError("Failed to generate content")
                time.sleep(1)  # Wait before retrying

# Routes
@app.before_request
def before_request():
    g.request_start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(g, 'request_start_time'):
        elapsed = time.time() - g.request_start_time
        logging.info(f"Request processed in {elapsed:.2f} seconds")
    return response

@app.route('/')
def index():
    return send_from_directory(os.getcwd(), 'index.html')

@app.route('/generate_content', methods=['POST'])
def generate_content():
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({"error": "URL is required"}), 400

        if not WebScraper.is_valid_url(url):
            return jsonify({"error": "Invalid URL format"}), 400

        if not WebScraper.is_allowed_domain(url):
            return jsonify({"error": "Domain not allowed"}), 403

        # Scrape content
        content = WebScraper.scrape_content(url)
        if not content:
            return jsonify({"error": "No content found at URL"}), 400

        # Extract keywords
        keywords = ContentGenerator.extract_keywords(content)
        if not keywords:
            return jsonify({"error": "Failed to extract keywords"}), 400

        # Generate content
        prompt = f"""Based on the following keywords, write a comprehensive article:
        Keywords: {', '.join(keywords)}
        
        Please make sure the content is:
        - Well-structured with clear paragraphs
        - Engaging and informative
        - Between 400-600 words
        - Written in a professional tone
        """
        
        generated_content = ContentGenerator.generate_content(prompt)
        if not generated_content:
            return jsonify({"error": "Failed to generate content"}), 500

        # Prepare response data
        response_data = {
            "url": url,
            "keywords": keywords,
            "generated_content": generated_content,
            "timestamp": datetime.now().isoformat()
        }

        # Save to history
        save_to_history(response_data)

        return jsonify(response_data)

    except ContentFetchError as e:
        return jsonify({"error": str(e)}), 400
    except ProcessingError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/history')
def get_history():
    try:
        history = read_history()
        return render_template('history.html', history=history)
    except Exception as e:
        logging.error(f"Error fetching history: {e}")
        return jsonify({"error": "Failed to fetch history"}), 500

@app.route('/api/analytics')
def get_analytics():
    try:
        history = read_history()
        
        # Calculate analytics
        analytics = {
            "total_generations": len(history),
            "keywords": {},
            "timeline": {},
            "average_word_count": 0,
            "average_keywords": 0
        }
        
        total_words = 0
        total_keywords = 0
        
        for entry in history:
            # Process keywords
            for keyword in entry["keywords"]:
                analytics["keywords"][keyword] = analytics["keywords"].get(keyword, 0) + 1
            
            # Process timeline
            date = entry["timestamp"][:10]
            analytics["timeline"][date] = analytics["timeline"].get(date, 0) + 1
            
            # Calculate averages
            if "metadata" in entry:
                total_words += entry["metadata"]["word_count"]
                total_keywords += entry["metadata"]["keyword_count"]
        
        if history:
            analytics["average_word_count"] = total_words / len(history)
            analytics["average_keywords"] = total_keywords / len(history)
        
        # Convert timeline to list format
        analytics["timeline"] = [
            {"date": date, "count": count}
            for date, count in analytics["timeline"].items()
        ]
        
        return jsonify(analytics)
        
    except Exception as e:
        logging.error(f"Analytics error: {e}")
        return jsonify({"error": "Failed to fetch analytics"}), 500

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(429)
def ratelimit_error(error):
    return jsonify({"error": "Rate limit exceeded"}), 429

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'True').lower() == 'true')
