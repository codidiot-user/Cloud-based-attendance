import google.generativeai as genai
from datetime import datetime
import psycopg2 # The new library for the cloud DB
import streamlit as st

# We'll pass the API key from the dashboard
def configure_ai(api_key):
    genai.configure(api_key=api_key)

class SLM_Assistant:
    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.model = genai.GenerativeModel('gemini-1.5-flash') # Use the fast Gemini model
        
        # The prompt is exactly the same as before!
        self.system_prompt = """
        You are a smart assistant for an attendance system...
        ...
        (Your entire "tool-router" prompt goes here)
        ...
        Response: non_attendance,null
        """

    def _get_ai_decision(self, user_question):
        """Asks the AI to choose a tool and parses the simple string response."""
        today = datetime.now().strftime('%Y-%m-%d')
        prompt = self.system_prompt.format(today_date=today)
        
        try:
            # This is the new part: calling the Gemini API
            full_prompt = prompt + "\n\nUser: " + user_question + "\nResponse:"
            response = self.model.generate_content(full_prompt)
            decision_str = response.text.strip()
            
            # The rest of the parsing is the same
            parts = decision_str.split(',')
            tool = parts[0].strip()
            date = parts[1].strip() if len(parts) > 1 else None
            if date == 'null': date = None
            return {"tool": tool, "date": date}
        except Exception as e:
            print(f"Error parsing AI decision: {e}")
            return {"tool": "non_attendance", "date": None}

    # The entire process_question function is exactly the same
    # just make sure it's using psycopg2, which it will
    # because it uses the 'db_connection' we pass it.
    def process_question(self, user_question: str) -> str:
        # ... (This entire function is UNCHANGED) ...
        # (It uses 'self.db_connection.cursor()', which is correct)
        pass # Placeholder for your existing function

    # ... (Your other helper functions are UNCHANGED) ...

    pass # Placeholder for your existing functions
