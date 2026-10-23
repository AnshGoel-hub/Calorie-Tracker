# Calorie Tracker with Backend

1. Activate your Python environment (such as `development env`).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the backend server:
   ```bash
   python main.py
   ```
4. Open `index.html` in your web browser. 
   It will automatically connect to the backend at http://127.0.0.1:8000 to save and load data. (If the backend is not running, the application will still function seamlessly using local storage, allowing you to use it offline).

## API Integration Note
The HTML file is configured to use the Gemini REST API for automatic food nutrition lookups. Click "Estimate with Gemini" for unknown foods, and the browser will securely prompt you for your Gemini API Key directly, without needing to hardcode it in the frontend file.
