# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy and install requirements (cached layer unless requirements.txt changes)
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Copy files
COPY chat2db /app/chat2db/
COPY db /app/db/
COPY .env /app/

# Expose the Streamlit port
EXPOSE 8501

# Set the working directory to the chat2db folder
WORKDIR /app/chat2db

# Run Streamlit with unbuffered output (to see prints in the Docker logs)
CMD ["python", "-u", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
