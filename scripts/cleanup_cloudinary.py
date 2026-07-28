#!/usr/bin/env python3
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

def cloudinary_config():
    cloudinary_url = os.getenv("CLOUDINARY_URL", "")
    if cloudinary_url:
        parsed = urllib.parse.urlparse(cloudinary_url)
        return parsed.hostname, parsed.username, parsed.password
    return (
        os.getenv("CLOUDINARY_CLOUD_NAME"),
        os.getenv("CLOUDINARY_API_KEY"),
        os.getenv("CLOUDINARY_API_SECRET"),
    )

def main():
    cloud_name, api_key, api_secret = cloudinary_config()
    if not cloud_name or not api_key or not api_secret:
        print("Notice: Cloudinary env missing; skipping cleanup.")
        return

    folder = os.getenv("CLOUDINARY_FOLDER", "thechessstuff")
    print(f"Cleaning up old videos in Cloudinary folder '{folder}'...")

if __name__ == "__main__":
    main()
