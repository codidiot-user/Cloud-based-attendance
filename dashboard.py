import streamlit as st
import psycopg2
from psycopg2.extras import DictCursor # Needed for the helper function
from ai_assistant import SLM_Assistant, configure_ai # Import your AI class and configure function

st.set_page_config(page_title="Attendance AI Assistant", layout="centered")
st.title("🤖 Attendance AI Assistant")

# --- Database Connection Function (uses Streamlit Secrets) ---
@st.cache_resource # Cache the connection for performance
def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=st.secrets["db_host"],
            database=st.secrets["db_name"],
            user=st.secrets["db_user"],
            password=st.secrets["db_password"],
            port=st.secrets["db_port"]
        )
        return connection
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None

# --- Configure Google AI (uses Streamlit Secrets) ---
try:
    GOOGLE_API_KEY = st.secrets["google_api_key"]
    configure_ai(GOOGLE_API_KEY)
except KeyError:
    st.error("Google AI API key not found in Streamlit secrets. Please add it.")
    st.stop() # Stop the app if the key is missing

# --- Main App Logic ---
conn = get_db_connection()

# Use the corrected connection check for psycopg2
if conn and conn.closed == 0:
    st.success("Successfully connected to the attendance database!")
    
    # Instantiate the assistant
    assistant = SLM_Assistant(conn)
    
    # Get user input
    user_question = st.text_input("Ask any question about the attendance records:", placeholder="e.g., Who was absent today?")
    
    # Process the question when the button is clicked
    if st.button("Get Answer"):
        if user_question:
            with st.spinner("🧠 Thinking..."):
                # Call the main processing function from the assistant
                answer = assistant.process_question(user_question)
                st.markdown("---")
                # Display the answer using markdown for better formatting (like lists)
                st.markdown(f"### Answer\n{answer}") 
        else:
            st.warning("Please enter a question.")
else:
    # Update error message for clarity
    st.error("Failed to connect to the database. Please check Streamlit secrets and Supabase status.")
