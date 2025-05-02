# OAuth Callback Handler

This document describes how to handle the OAuth callback in your frontend application to detect new users and provide them with an appropriate onboarding experience.

## Overview

When a user completes OAuth authentication with Microsoft or Google, the backend redirects to:
```
/oauth/callback?token={token}&is_new_user={true|false}
```

The `is_new_user` parameter indicates whether this user has just been created in our database or is an existing user.

## Callback Handler Example (React)

Here's an example of how to handle this in a React application:

```jsx
// OAuthCallback.jsx
import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

function OAuthCallback() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    async function processCallback() {
      try {
        // Parse URL parameters
        const params = new URLSearchParams(location.search);
        const token = params.get('token');
        const isNewUser = params.get('is_new_user') === 'true';
        
        if (!token) {
          throw new Error('No authentication token received');
        }
        
        // Store the token in localStorage or your auth state management
        localStorage.setItem('auth_token', token);
        
        // Fetch user profile if needed
        // const userProfile = await fetchUserProfile(token);
        
        // Redirect based on whether the user is new or returning
        if (isNewUser) {
          // Redirect new users to onboarding flow
          navigate('/onboarding');
        } else {
          // Redirect returning users to dashboard
          navigate('/dashboard');
        }
      } catch (error) {
        console.error('OAuth callback error:', error);
        setError(error.message);
      } finally {
        setLoading(false);
      }
    }
    
    processCallback();
  }, [location, navigate]);
  
  if (loading) {
    return <div className="loading">Processing your login...</div>;
  }
  
  if (error) {
    return <div className="error">Error: {error}</div>;
  }
  
  return null;
}

export default OAuthCallback;
```

## Onboarding Flow for New Users

For new users, you should create an onboarding flow that may include:

1. Terms of Service acceptance
2. User profile completion (username, preferences, etc.)
3. Welcome tutorial
4. Interest selection

Example onboarding component:

```jsx
// Onboarding.jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Onboarding() {
  const [step, setStep] = useState(1);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [profile, setProfile] = useState({
    displayName: '',
    interests: [],
  });
  const navigate = useNavigate();
  
  const handleTermsAccept = () => {
    setTermsAccepted(true);
    setStep(2);
  };
  
  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    
    // Save profile to backend
    try {
      const token = localStorage.getItem('auth_token');
      await fetch('/api/users/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(profile)
      });
      
      // Move to next step
      setStep(3);
    } catch (error) {
      console.error('Error saving profile:', error);
    }
  };
  
  const completeOnboarding = () => {
    // Redirect to main application
    navigate('/dashboard');
  };
  
  return (
    <div className="onboarding">
      {step === 1 && (
        <div className="terms-step">
          <h2>Terms of Service</h2>
          <div className="terms-content">
            {/* Terms of service text */}
            <p>By using our service, you agree to our Terms of Service and Privacy Policy.</p>
          </div>
          <button 
            onClick={handleTermsAccept}
            disabled={!termsAccepted}
          >
            Continue
          </button>
          <label>
            <input 
              type="checkbox" 
              checked={termsAccepted}
              onChange={e => setTermsAccepted(e.target.checked)}
            />
            I accept the Terms of Service
          </label>
        </div>
      )}
      
      {step === 2 && (
        <div className="profile-step">
          <h2>Complete Your Profile</h2>
          <form onSubmit={handleProfileSubmit}>
            <div>
              <label>Display Name</label>
              <input
                type="text"
                value={profile.displayName}
                onChange={e => setProfile({...profile, displayName: e.target.value})}
                required
              />
            </div>
            
            <div>
              <label>Select Your Interests</label>
              {/* Interest selection checkboxes */}
              <div className="interest-options">
                {['AI', 'Machine Learning', 'Web Development', 'Mobile Development'].map(interest => (
                  <label key={interest}>
                    <input
                      type="checkbox"
                      checked={profile.interests.includes(interest)}
                      onChange={e => {
                        if (e.target.checked) {
                          setProfile({...profile, interests: [...profile.interests, interest]});
                        } else {
                          setProfile({...profile, interests: profile.interests.filter(i => i !== interest)});
                        }
                      }}
                    />
                    {interest}
                  </label>
                ))}
              </div>
            </div>
            
            <button type="submit">Save Profile</button>
          </form>
        </div>
      )}
      
      {step === 3 && (
        <div className="welcome-step">
          <h2>Welcome to the Platform!</h2>
          <p>Your account has been set up successfully.</p>
          <button onClick={completeOnboarding}>Get Started</button>
        </div>
      )}
    </div>
  );
}

export default Onboarding;
```

## Implementation Steps

1. Add the OAuthCallback component to your routes
2. Create an Onboarding flow for new users
3. Set up corresponding API endpoints to save user preferences/settings

## Route Configuration Example

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import OAuthCallback from './components/OAuthCallback';
import Onboarding from './components/Onboarding';
import Dashboard from './components/Dashboard';
import Login from './components/Login';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/oauth/callback" element={<OAuthCallback />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/dashboard" element={<Dashboard />} />
        {/* Other routes */}
      </Routes>
    </BrowserRouter>
  );
}

export default App;
``` 