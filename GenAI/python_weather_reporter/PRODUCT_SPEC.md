# Product Specification: AI Weather Reporter (Storrs)

## Overview
Develop a Python-based AI system that fetches weather data for Storrs, CT, stores it in Google Sheets, generates a catchy 8-second script, and produces a video featuring a human-like female reporter using Vertex AI Video 3.1 (Veo). The final video and script will be uploaded to Google Drive only after passing several quality and accuracy test cases.

## Technical Stack
- **Language**: Python
- **APIs**:
  - **Weather**: Google Custom Search API / Weather API
  - **Storage**: Google Sheets API
  - **Content**: Google Drive API
  - **Generative AI**: 
    - Vertex AI Gemini 1.5 Pro (for script generation & verification)
    - Vertex AI Video 3.1 / Veo (for video generation)
- **Validation**: Python-based test suite with AI-assisted verification.

## Data Flow
1. **Fetch**: Python script calls Google Weather API for Storrs, CT.
2. **Store**: Weather details (Expected weather, highs, lows, conditions) are logged to a Google Sheet.
3. **Script**: Gemini 1.5 Pro generates a catchy 8-second report script.
4. **Save Script**: Script saved as `.txt` in Google Drive.
5. **Video Gen**: Vertex AI Video 3.1 generates 8s video of a female reporter.
6. **Verification**: 
   - Script length (~8s).
   - Accuracy: Script content vs Sheet data.
   - Character Consistency: Recurring reporter appearance.
   - Background Harmony: Background matches weather condition.
7. **Upload**: Final video uploaded to Drive if it passes tests.

## Test Cases (Verification)
- **Correctness**: All spellings are English and correct.
- **Accuracy**: Weather data in script matches the historical sheet entry.
- **Visual Consistency**: Main character has similar appearance in recurring prompts.
- **Contextual Relevance**: Sunny weather = Sunny background; Snow = Snowy background.

## Delivery Phases
1. **Phase 1**: Product Specification (Current).
2. **Phase 2**: Weather & Google Sheets Integration.
3. **Phase 3**: Script generation & Google Drive upload.
4. **Phase 4**: Vertex AI Video 3.1 Integration.
5. **Phase 5**: Verification Logic & Final Pipeline.
