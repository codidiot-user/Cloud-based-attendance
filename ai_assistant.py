import google.generativeai as genai
from datetime import datetime
import psycopg2 # For cloud DB
import streamlit as st

# Function to configure the AI (called from dashboard.py)
def configure_ai(api_key):
    genai.configure(api_key=api_key)

class SLM_Assistant:
    def __init__(self, db_connection):
        self.db_connection = db_connection
        # Use the Gemini model via Google AI Studio
        self.model = genai.GenerativeModel('gemini-1.5-flash') 
        
        # --- FINALIZED "SIMPLE-STRING" PROMPT ---
        self.system_prompt ="""
        You are a smart assistant for an attendance system. Your only job is to analyze the user's question and choose the correct "tool" to answer it.
        
        You MUST respond with only two words, separated by a comma: "tool_name,date".
        The "date" must be in 'YYYY-MM-DD' format. Use today's date if the user says "today". Use 'null' if no date is needed. Today's date is {today_date}.

        --- AVAILABLE TOOLS ---
        -- Attendance Log Tools (Daily data) --
        - "get_present": For questions about who was present on a specific day.
        - "get_absent": For questions about who was absent on a specific day.
        - "get_present_count": For questions about the total count of students *present on a specific day*.
        - "get_first_arrival": For questions about who arrived first on a specific day.
        - "get_last_arrival": For questions about who arrived last on a specific day.
        - "get_late_arrivals": For questions about who was "late" (after 09:00:00) on a specific day.
        - "get_specific_student_status": For questions about a single student's *attendance status* (e.g., "Was Elon Musk present?").

        -- Student Table Tools (Permanent data) --
        - "get_student_info": For questions about one student's *permanent info* (e.g., "What is Bill Gates' roll number?").
        - "get_all_students": For questions asking to *list all students* and their roll numbers.
        - "get_total_student_count": For questions about the *total number of students enrolled* in the system.

        -- Other Tools --
        - "non_attendance": For any other question (e.g., "who are you?", "hello").

        --- EXAMPLES ---
        User: "Who was present today?"
        Response: get_present,{today_date}

        User: "Was Elon Musk present today?"
        Response: get_specific_student_status,{today_date}
        
        User: "What is Bill Gates' roll number?"
        Response: get_student_info,null

        User: "who came in first today?"
        Response: get_first_arrival,{today_date}
        
        # --- NEW EXAMPLE ADDED HERE ---
        User: "Who was the last person entered today?"
        Response: get_last_arrival,{today_date}
        # --- END OF NEW EXAMPLE ---

        User: "who are you?"
        Response: non_attendance,null
        """

    def _get_ai_decision(self, user_question):
        """Asks the AI to choose a tool and parses the simple string response."""
        today = datetime.now().strftime('%Y-%m-%d')
        prompt = self.system_prompt.format(today_date=today)
        
        try:
            # Use the Google AI API
            full_prompt = prompt + "\n\nUser: " + user_question + "\nResponse:"
            response = self.model.generate_content(full_prompt)
            decision_str = response.text.strip()
            
            # Parse the simple "tool,date" string
            parts = decision_str.split(',')
            tool = parts[0].strip()
            date = parts[1].strip() if len(parts) > 1 else None
            
            if date == 'null': date = None
                
            return {"tool": tool, "date": date}
        
        except Exception as e:
            print(f"Error parsing AI decision: {e}")
            # Fallback to non_attendance if AI fails
            return {"tool": "non_attendance", "date": None}

    def process_question(self, user_question: str) -> str:
        """Main function to route the question to the correct tool."""
        decision = self._get_ai_decision(user_question)
        tool = decision.get("tool")
        date = decision.get("date")

        st.code(f"AI Decision: {decision}", language="json") # Show the AI's choice

        try:
            cursor = self.db_connection.cursor()
            
            # --- ATTENDANCE TOOLS ---
            if tool == "get_present":
                # Use %s placeholders for psycopg2
                sql = "SELECT s.student_name FROM students s JOIN attendance_log al ON s.roll_no = al.student_roll_no WHERE al.attendance_date = %s ORDER BY s.student_name ASC"
                cursor.execute(sql, (date,))
                results = [row[0] for row in cursor.fetchall()]
                return f"The following students were present on {date}: {', '.join(results)}" if results else f"No students were found present on {date}."

            elif tool == "get_absent":
                sql = "SELECT student_name FROM students WHERE roll_no NOT IN (SELECT student_roll_no FROM attendance_log WHERE attendance_date = %s) ORDER BY student_name ASC"
                cursor.execute(sql, (date,))
                results = [row[0] for row in cursor.fetchall()]
                return f"The following students were absent on {date}: {', '.join(results)}" if results else f"No students were listed as absent on {date}."

            elif tool == "get_present_count":
                sql = "SELECT COUNT(student_roll_no) FROM attendance_log WHERE attendance_date = %s"
                cursor.execute(sql, (date,))
                count = cursor.fetchone()[0]
                return f"There were a total of {count} students present on {date}."

            elif tool == "get_first_arrival":
                sql = "SELECT s.student_name, al.in_time FROM students s JOIN attendance_log al ON s.roll_no = al.student_roll_no WHERE al.attendance_date = %s ORDER BY al.in_time ASC LIMIT 1"
                cursor.execute(sql, (date,))
                result = cursor.fetchone()
                return f"The first student to arrive on {date} was {result[0]} at {result[1]}." if result else f"No arrival times were found for {date}."

            elif tool == "get_last_arrival":
                sql = "SELECT s.student_name, al.in_time FROM students s JOIN attendance_log al ON s.roll_no = al.student_roll_no WHERE al.attendance_date = %s ORDER BY al.in_time DESC LIMIT 1"
                cursor.execute(sql, (date,))
                result = cursor.fetchone()
                return f"The last student to arrive on {date} was {result[0]} at {result[1]}." if result else f"No arrival times were found for {date}."

            elif tool == "get_late_arrivals":
                LATE_TIME_THRESHOLD = "09:00:00"
                sql = "SELECT s.student_name, al.in_time FROM students s JOIN attendance_log al ON s.roll_no = al.student_roll_no WHERE al.attendance_date = %s AND al.in_time > %s ORDER BY al.in_time ASC"
                cursor.execute(sql, (date, LATE_TIME_THRESHOLD))
                results = cursor.fetchall()
                if not results: return f"No students were marked as late (after {LATE_TIME_THRESHOLD}) on {date}."
                late_students = [f"{row[0]} (at {row[1]})" for row in results]
                return f"The following students were late on {date}: {', '.join(late_students)}."
            
            elif tool == "get_specific_student_status":
                name = next((s['student_name'] for s_id, s in self._get_all_students().items() if s['student_name'] in user_question.upper()), None)
                if not name: return "I couldn't identify a specific student in your question. Please try again."
                sql = "SELECT s.student_name FROM students s JOIN attendance_log al ON s.roll_no = al.student_roll_no WHERE al.attendance_date = %s AND s.student_name = %s"
                cursor.execute(sql, (date, name))
                result = cursor.fetchone()
                return f"Yes, {name} was present on {date}." if result else f"No, {name} was not marked present on {date}."
            
            # --- STUDENT INFO TOOLS ---
            elif tool == "get_student_info":
                name = next((s['student_name'] for s_id, s in self._get_all_students().items() if s['student_name'] in user_question.upper()), None)
                if not name: return "I couldn't identify a specific student in your question. Please try again."
                sql = "SELECT roll_no FROM students WHERE student_name = %s"
                cursor.execute(sql, (name,))
                result = cursor.fetchone()
                return f"The roll number for {name} is {result[0]}." if result else f"I could not find a student named {name}."

            elif tool == "get_all_students":
                sql = "SELECT roll_no, student_name FROM students ORDER BY student_name ASC"
                cursor.execute(sql)
                results = cursor.fetchall()
                if not results: return "There are no students enrolled in the system."
                # Format the output nicely for Streamlit's markdown
                all_students_str = "\n".join([f"- {row[1]} (Roll No: {row[0]})" for row in results])
                return f"Here is the list of all enrolled students:\n{all_students_str}"

            elif tool == "get_total_student_count":
                sql = "SELECT COUNT(roll_no) FROM students"
                cursor.execute(sql)
                count = cursor.fetchone()[0]
                return f"There are a total of {count} students enrolled in the system."
            
            # --- OTHER TOOLS ---
            else: # non_attendance
                # Simple hardcoded responses for chit-chat
                if "who made you" in user_question.lower():
                    return "I am an AI assistant created by Google and fine-tuned for this attendance system by you!"
                elif "who are you" in user_question.lower():
                    return "I am an AI assistant designed to help you query the student attendance database."
                return "I'm sorry, I can only answer questions related to student attendance."
        
        except Exception as err: # Catch potential database errors
            # Provide a user-friendly error message
            st.error(f"An error occurred: {err}") 
            return "Sorry, I encountered a problem trying to answer your question."
        finally:
            # Ensure the cursor is always closed
            if cursor:
                cursor.close()

    @st.cache_data # Use Streamlit's caching for efficiency
    def _get_all_students(_self):
        """Helper to get all student names for matching. Cached."""
        # Use DictCursor for easier access by column name
        cursor = _self.db_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT roll_no, student_name FROM students")
        # Structure data for easy lookup
        students = {s['roll_no']: {'student_name': s['student_name']} for s in cursor.fetchall()}
        cursor.close()
        return students

# --- Need to import DictCursor ---
# Place this near the top imports if not already there
from psycopg2.extras import DictCursor

