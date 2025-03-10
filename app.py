from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import datetime
import time
import subprocess
import os
from pydantic import BaseModel  
from helper import monitor_meeting, google_login
from config import config


app = FastAPI()
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
OAUTH2_SCHEME = OAuth2AuthorizationCodeBearer(
    tokenUrl="/auth/google",
    authorizationUrl="https://accounts.google.com/o/oauth2/auth"  # Add this URL
)

@app.get("/auth/google")
def authenticate_google():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return {"access_token": creds.token, "refresh_token": creds.refresh_token}

@app.get("/meetings")
def get_meetings(token: str = Depends(OAUTH2_SCHEME)):
    creds = Credentials(token=token)
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    one_week_later = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=one_week_later,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    meetings = []

    for event in events:
        meeting_url = event.get('hangoutLink')
        if meeting_url:
            meetings.append({"title": event['summary'], "url": meeting_url})

    return meetings

class MeetingRequest(BaseModel):
    meeting_url: str



# def google_login(driver):
#     driver.get("https://accounts.google.com/signin")
#     time.sleep(5)

#     email_input = driver.find_element(By.XPATH, "//input[@type='email']")
#     email_input.send_keys(GOOGLE_EMAIL)
#     driver.find_element(By.XPATH, "//*[text()='Next']").click()
#     time.sleep(5)

#     password_input = driver.find_element(By.XPATH, "//input[@type='password']")
#     password_input.send_keys(GOOGLE_PASSWORD)
#     driver.find_element(By.XPATH, "//*[text()='Next']").click()
#     time.sleep(10)
#     print("Logged into Google")


def start_recording(output_file):
    import subprocess

    resolution = subprocess.check_output("xdpyinfo | grep 'dimensions:' | awk '{print $2}'", shell=True).decode().strip()
    print(f"Detected Screen Resolution: {resolution}")

    print("Recording Started...")
    return subprocess.Popen(
        ["ffmpeg", "-f", "x11grab", "-video_size", resolution, "-i", ":0.0", output_file]
    )

    
def join_meeting(meeting_url):

    print("Starting Virtual Display...")
    subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1536x864x16", "-ac"])
    os.environ['DISPLAY'] = ':99'

    options = webdriver.ChromeOptions()

    options.add_argument("--use-fake-ui-for-media-stream")  # Allow mic and camera automatically
    options.add_argument("--disable-popup-blocking")        # Block popup windows
    options.add_argument("--start-maximized")               # Start in maximized window
    options.add_argument("--disable-gpu")                   # Fix black screen issue


    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    google_login(driver)  # Login before opening meeting link
    driver.get(meeting_url)
    time.sleep(10)

    try:
        try:
            camera_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Turn off camera' or @data-tooltip='Turn off camera (ctrl + e)']"))
            )
            camera_button.click()
            print("Camera Turned Off")
        except TimeoutException:
            print("Camera button not found")


        try:
            mic_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Turn off microphone' or @data-tooltip='Turn off microphone (ctrl + d)']"))
            )
            mic_button.click()
            print("Microphone Turned Off")
        except TimeoutException:
            print("Microphone button not found")


        try:
            join_btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Ask to join')]"))
            )
        except TimeoutException:
            print("Ask to join button not found, trying Join now...")
            join_btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Join now')]"))
            )
        join_btn.click()

        recording_process = subprocess.Popen([
            "ffmpeg",
            "-y",                
            "-f", "x11grab",          
            "-r", "30",               
            "-video_size", "1536x864",  
            "-i", ":99.0+0,0",         
            "-f", "pulse",             
            "-i", "default",           
            "-ac", "2",               
            "-ar", "44100",            
            "-codec:v", "libx264",
            "-preset", "ultrafast",
            "-codec:a", "aac",         
            "-b:a", "128k",            
            "recording.mp4"
        ])


        monitor_meeting(driver, recording_process)
        
        print("Bot left the Meeting")

    except Exception as e:
        print(f"Failed: {e}")
    finally:
        driver.quit()
        print("Driver closed")



@app.post("/start-bot")
def start_bot(meeting: MeetingRequest, token: str = Depends(OAUTH2_SCHEME)):
    meeting_url = meeting.meeting_url
    join_meeting(meeting_url)
    return {"status": "Bot requested to join and recording started"}


# @app.post("/upload")
# def upload_recording():
#     url = "https://api.lingo.ai/upload"
#     files = {'file': open("recording.mp4", 'rb')}
#     response = requests.post(url, files=files)
#     os.remove("recording.mp4")
#     return response.json()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
