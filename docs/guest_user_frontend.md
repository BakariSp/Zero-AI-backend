# Guest User Frontend Implementation Guide

This document provides guidance for implementing guest user functionality in the frontend application.

## Overview

The backend now supports guest users who can use the application without logging in. Guest users can:
- Browse learning paths and content
- Create and save their own learning paths
- Track progress on courses and learning paths
- Later upgrade to a real account, preserving all their data

## API Endpoints

### Create Guest User
```
POST /api/auth/guest
```
Response:
```json
{
  "id": 123,
  "is_guest": true,
  "token": "jwt_token_here",
  "created_at": "2023-05-01T12:00:00Z"
}
```

### Merge Guest Account into Regular Account
```
POST /api/auth/merge
```
Request body:
```json
{
  "guest_id": 123
}
```
Response:
```json
{
  "status": "merged",
  "real_user_id": 456,
  "guest_id": 123,
  "message": "Successfully merged guest account data into your account"
}
```

### Keep Guest User Active
```
PUT /api/auth/guest/activity
```
Response:
```json
{
  "status": "updated",
  "message": "Guest user activity timestamp updated"
}
```

## Frontend Implementation Steps

1. **Add Guest Login Option**
   - Add a "Continue as Guest" button to your login/signup page
   - When clicked, call the `/api/auth/guest` endpoint
   - Store the returned token in localStorage just like a regular auth token
   - Save the guest user ID to use later during account upgrade

2. **Session Management**
   - Use the same authentication flow for both guest and regular users
   - The backend JWT handler will automatically recognize guest tokens
   - Add a "heartbeat" to periodically call `/api/auth/guest/activity` to keep the guest account active

3. **Conversion Flow**
   - Show a persistent banner or reminder to guest users encouraging them to create an account
   - When a guest user signs up or logs in, call the `/api/auth/merge` endpoint with their guest ID
   - After successful merge, update the token to the new user's token
   - Display a success message showing that their data has been preserved

4. **UI Customization**
   - Visually indicate when a user is in guest mode
   - Restrict premium features if needed (based on your business rules)
   - Provide clear benefits to upgrading to a full account

## Example: Authentication Service

```typescript
// auth.service.ts
import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, interval } from 'rxjs';
import { tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'https://your-api-url.com/api';
  private readonly GUEST_USER_KEY = 'guest_user_id';
  private readonly TOKEN_KEY = 'auth_token';
  private heartbeatInterval: any;

  constructor(private http: HttpClient) {
    this.startHeartbeatIfGuest();
  }

  // Create a guest user account
  continueAsGuest(): Observable<any> {
    return this.http.post(`${this.apiUrl}/auth/guest`, {}).pipe(
      tap(response => {
        localStorage.setItem(this.TOKEN_KEY, response.token);
        localStorage.setItem(this.GUEST_USER_KEY, response.id);
        this.startHeartbeatIfGuest();
      })
    );
  }

  // Regular login
  login(email: string, password: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/token`, { username: email, password }).pipe(
      tap(response => {
        localStorage.setItem(this.TOKEN_KEY, response.access_token);
        
        // Check if there was a guest account to merge
        const guestId = this.getGuestUserId();
        if (guestId) {
          this.mergeGuestAccount(guestId).subscribe();
        }
        
        this.stopHeartbeat();
      })
    );
  }

  // Merge guest account into regular account
  mergeGuestAccount(guestId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/auth/merge`, { guest_id: guestId }).pipe(
      tap(response => {
        localStorage.removeItem(this.GUEST_USER_KEY);
      })
    );
  }

  // Update guest user activity timestamp
  updateGuestActivity(): Observable<any> {
    return this.http.put(`${this.apiUrl}/auth/guest/activity`, {});
  }

  // Get stored guest user ID
  getGuestUserId(): number | null {
    const id = localStorage.getItem(this.GUEST_USER_KEY);
    return id ? parseInt(id, 10) : null;
  }

  // Check if current user is a guest
  isGuestUser(): boolean {
    return !!this.getGuestUserId();
  }

  // Start the heartbeat to keep guest user active
  startHeartbeatIfGuest() {
    if (this.isGuestUser() && !this.heartbeatInterval) {
      // Send heartbeat every 20 minutes
      this.heartbeatInterval = interval(20 * 60 * 1000).subscribe(() => {
        this.updateGuestActivity().subscribe();
      });
    }
  }

  // Stop the heartbeat when user logs in or out
  stopHeartbeat() {
    if (this.heartbeatInterval) {
      this.heartbeatInterval.unsubscribe();
      this.heartbeatInterval = null;
    }
  }

  // Logout (works for both guest and regular users)
  logout() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.GUEST_USER_KEY);
    this.stopHeartbeat();
  }
}
```

## Important Considerations

1. **Security**: Always treat guest users with the same security considerations as regular users.

2. **Data Privacy**: Inform users about what data is stored and how it will be transferred when upgrading.

3. **Expiration**: Guest accounts expire after 30 days of inactivity. Make this clear to users.

4. **Performance**: Consider lazy-loading user data to improve initial load times for guest users.

5. **Token Handling**: Guest tokens have longer expiration times than regular user tokens.

## Testing Checklist

- [ ] Guest user creation works
- [ ] Guest users can access all standard features
- [ ] Activity heartbeat updates the last_active_at timestamp
- [ ] Account merging successfully preserves all user data
- [ ] UI clearly indicates guest status
- [ ] Upgrade prompts are shown at appropriate times

For any questions or issues, contact the backend team. 