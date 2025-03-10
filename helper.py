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
from config import config



GOOGLE_EMAIL = config.GOOGLE_EMAIL
GOOGLE_PASSWORD = config.GOOGLE_PASSWORD

def get_participant_count(driver):
    """Extracts the current participant count from Google Meet UI."""
    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[div[text()='People']]/following-sibling::div"))
        )
        return int(element.text.strip())
    except Exception as e:
        print("Error getting participant count:", e)
        return None  # Return None if unable to get the count

def monitor_meeting(driver, recording_process):
    """Monitors participant count and stops recording when only one participant is left."""
    while True:
        count = get_participant_count(driver)
        if count is not None:
            print(f"Current Participant Count: {count}")
            if count == 1:
                print("Only one participant left. Stopping recording...")
                stop_recording(recording_process)
                break
        time.sleep(5)  # Check every 5 seconds

def stop_recording(recording_process):
    """Stops the ffmpeg recording process."""
    print("Stopping the recording process...")
    recording_process.terminate()
    recording_process.wait()
    print("Recording Stopped.")


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