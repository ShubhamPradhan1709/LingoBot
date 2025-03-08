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

GOOGLE_EMAIL = "lingonotetakerbot@gmail.com"
GOOGLE_PASSWORD = "LingoNotetaker@123"


def google_login(driver):
    driver.get("https://accounts.google.com/signin")
    
    try:
        # Wait until Email Field is visible and clickable
        email_input = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='email']"))
        )
        email_input.send_keys(GOOGLE_EMAIL)
        driver.find_element(By.XPATH, "//*[text()='Next']").click()
        print("Entered Email")

        # Wait for Password Field
        password_input = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='password']"))
        )
        password_input.send_keys(GOOGLE_PASSWORD)
        driver.find_element(By.XPATH, "//*[text()='Next']").click()
        print("Entered Password")

        # Wait for Redirect to Google Page
        WebDriverWait(driver, 20).until(
            EC.url_contains("myaccount.google.com")
        )
        print("Logged into Google")

    except TimeoutException:
        print("Login Failed: Element not found or not interactable")
    except Exception as e:
        print(f"Login Failed: {e}")

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

# def get_participant_count(driver):
#     try:
#         element = driver.find_element(By.XPATH, "//span[@class='rua5Nb']")
#         return int(element.text)
#     except Exception:
#         return -1
    
    
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

        # # Start Recording
        # recording_process = subprocess.Popen([
        #     "ffmpeg",
        #     "-y",                      # Overwrite existing file
        #     "-f", "x11grab",          # Screen recording for Linux
        #     "-r", "30",               # Frame rate
        #     "-video_size", "1536x864", # Screen size
        #     "-i", ":0.0",             # Display screen
        #     "-codec:v", "libx264",    # High-quality video
        #     "-preset", "ultrafast",   # Fast recording
        #     "recording.mp4"
        # ])

        recording_process = subprocess.Popen([
            "ffmpeg",
            "-y",                      # Overwrite if file exists
            "-f", "x11grab",          # Screen capture for Xvfb
            "-r", "30",               # Frame rate
            "-video_size", "1536x864", # Resolution
            "-i", ":99.0+0,0",        # Virtual display
            "-draw_mouse", "1",       # Show mouse cursor
            "-codec:v", "libx264",
            "-preset", "ultrafast",
            "recording.mp4"
        ])
        time.sleep(30)  # Just for testing

        # Stop Recording
        recording_process.terminate()
        recording_process.wait()
        
        print("Bot Joined Meeting")

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


@app.post("/upload")
def upload_recording():
    url = "https://api.lingo.ai/upload"
    files = {'file': open("recording.mp4", 'rb')}
    response = requests.post(url, files=files)
    os.remove("recording.mp4")
    return response.json()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
