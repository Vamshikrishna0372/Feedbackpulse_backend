"""
Quick API Test Script for FeedbackPulse Multi-Company Architecture
Run this after starting the backend server to verify everything works.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_company_search():
    """Test company autocomplete search"""
    print("\n1️⃣ Testing Company Search...")
    response = requests.get(f"{BASE_URL}/companies/search", params={"query": "amazon", "limit": 5})
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        companies = response.json()
        print(f"Found {len(companies)} companies:")
        for company in companies:
            print(f"  - {company['name']} ({company['slug']})")
    else:
        print(f"Error: {response.text}")

def test_admin_login():
    """Test admin authentication"""
    print("\n2️⃣ Testing Admin Login...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "admin@gmail.com", "password": "admin123"}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"✅ Login successful! Token: {token[:50]}...")
        return token
    else:
        print(f"❌ Login failed: {response.text}")
        return None

def test_list_feedback(token):
    """Test listing feedback with company isolation"""
    print("\n3️⃣ Testing List Feedback...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/admin/feedback", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        feedbacks = response.json()
        print(f"Found {len(feedbacks)} feedback items")
        for fb in feedbacks[:3]:
            print(f"  - [{fb['rating']}⭐] {fb['message'][:50]}... (Pinned: {fb['isPinned']})")
    else:
        print(f"Error: {response.text}")

def test_admin_profile(token):
    """Test admin profile endpoint"""
    print("\n4️⃣ Testing Admin Profile...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/admin/profile", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        profile = response.json()
        print(f"✅ Profile loaded:")
        print(f"  - Name: {profile.get('fullName')}")
        print(f"  - Email: {profile.get('email')}")
        print(f"  - Company: {profile.get('companyId')}")
    else:
        print(f"❌ Error: {response.text}")

def run_all_tests():
    """Run all API tests"""
    print("=" * 60)
    print("🧪 FeedbackPulse Multi-Company API Test Suite")
    print("=" * 60)
    
    try:
        # Test 1: Company Search
        test_company_search()
        
        # Test 2: Login
        token = test_admin_login()
        if not token:
            print("\n❌ Cannot proceed without authentication token")
            return
        
        # Test 3: List Feedback
        test_list_feedback(token)
        
        # Test 4: Admin Profile
        test_admin_profile(token)
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to backend server!")
        print("Make sure the server is running: python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    run_all_tests()
