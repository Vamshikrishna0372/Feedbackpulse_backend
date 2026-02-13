
import requests
import json

def test_login():
    url = "http://127.0.0.1:8000/auth/login"
    
    # Test 1: Company Admin
    payload1 = {"email": "Krish@gmail.com", "password": "admin123"}
    print(f"Testing Company Admin: {payload1['email']}...")
    try:
        r1 = requests.post(url, json=payload1)
        print(f"Status: {r1.status_code}")
        print(f"Body: {r1.text}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Platform Admin (Main Admin)
    payload2 = {"email": "admin@gmail.com", "password": "admin123"}
    print(f"\nTesting Main Admin: {payload2['email']}...")
    try:
        r2 = requests.post(url, json=payload2)
        print(f"Status: {r2.status_code}")
        print(f"Body: {r2.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
