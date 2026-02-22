# AI Weather Reporter for Storrs, CT

This project automates the creation of an AI-generated weather report video for Storrs, CT.

## Setup Instructions

### 1. Google Cloud Credentials
- Enable **Google Sheets API**, **Google Drive API**, and **Vertex AI API** in your Google Cloud Console.
- Create an **OAuth 2.0 Client ID (Desktop App)**.
- Download the credentials JSON and save it as `credentials.json` in the project root.
- Set the `GOOGLE_CLOUD_PROJECT` environment variable.

### 2. Install Dependencies
```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 requests pandas google-cloud-aiplatform
```

### 3. Usage
Run the main script:
```bash
python main.py
```

## How it Works
1. **Weather Fetch**: Uses `weather_service.py` to get the latest conditions for Storrs.
2. **Sheet Log**: Appends data to "Storrs AI Weather Data" spreadsheet via `sheets_service.py`.
3. **Script Gen**: Gemini 1.5 Pro generates a catchy 8s script, saved to Drive.
4. **Validation**: `validator.py` checks script content, spellings, and video prompt consistency.
5. **Video Gen**: If tests pass, Vertex AI Video 3.1 (Veo) generates an 8s video of Maya, the weather reporter.
6. **Final Save**: The video is uploaded to Google Drive.

## Validation Suite
The pipeline includes rigorous test cases:
- **Accuracy**: Ensures script data matches weather data.
- **Language**: Only English and correct spellings allowed.
- **Consistency**: Recurring prompts for the character "Maya" ensure similar appearance.
- **Context**: Background is dynamically adjusted (e.g., sunny vs. rainy) to match conditions.
