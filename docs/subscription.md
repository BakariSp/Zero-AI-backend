# Zero AI Subscription System

The Zero AI platform offers a tiered subscription model to accommodate different user needs, from casual learners to professional developers. This document provides API details and examples for implementing subscription features in the frontend.

## Subscription Tiers

| Feature | Free | Standard | Premium |
|---------|------|----------|---------|
| Daily Learning Paths | 3 | 10 | 100 |
| Daily Flashcards | 20 | 50 | 500 |
| Custom Sections | ✓ | ✓ | ✓ |
| AI Learning Assistant | Limited | ✓ | ✓ |
| Priority Support | ✗ | ✓ | ✓ |
| Advanced Analytics | ✗ | ✗ | ✓ |

## Daily Generation Limits

Each subscription tier has specific daily limits for generating content:

- **Free Tier**:
  - 3 learning paths per day
  - 20 cards per day
  - Basic features only

- **Standard Tier**:
  - 10 learning paths per day
  - 50 cards per day
  - All basic features plus priority support

- **Premium Tier**:
  - 100 learning paths per day
  - 500 cards per day
  - Access to all features including advanced analytics

Unlike the previous version, there are now no general account-wide limits. Users can save as many learning paths and cards as they want, regardless of subscription tier. The limits only apply to how many new items can be generated each day.

## How Daily Limits Work

The platform includes daily usage limits to ensure fair use of resources:
- Limits apply to generating new learning paths and cards
- Counts reset automatically at the start of each day (midnight UTC)
- Once you reach your daily limit, you'll need to wait until the next day to generate more content
- Viewing, editing, or using existing content is not affected by these limits

## Subscription Duration

Subscriptions are time-based with the following characteristics:
- **Free tier**: Never expires
- **Paid tiers** (Standard and Premium):
  - Have a specific start date and expiry date
  - Default subscription period is 30 days
  - Can be extended during purchase or renewal
  - Status is tracked (active or expired)

## API Endpoints for Subscription Management

### Get Daily Usage Information

**Endpoint:**
```
GET /api/daily-usage/me
```

**Authentication:**
Requires a valid JWT token in the Authorization header.

**Response:**
```json
{
  "paths": {
    "used": 2,
    "limit": 3,
    "remaining": 1
  },
  "cards": {
    "used": 15,
    "limit": 20,
    "remaining": 5
  },
  "subscription_tier": "free",
  "usage_date": "2023-10-30"
}
```

**Frontend Usage Example:**
```javascript
// React example using fetch
const fetchDailyUsage = async () => {
  try {
    const response = await fetch('/api/users/me/daily-usage', {
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch usage data');
    }
    
    const usageData = await response.json();
    
    // Display usage information to user
    setPathsRemaining(usageData.paths.remaining);
    setCardsRemaining(usageData.cards.remaining);
    
    // Check if user has reached limits
    if (usageData.paths.remaining <= 0) {
      setPathLimitReached(true);
      showNotification('You have reached your daily limit for learning paths');
    }
  } catch (error) {
    console.error('Error fetching daily usage:', error);
  }
};
```

### Get Subscription Information

**Endpoint:**
```
GET /api/subscription
```

**Authentication:**
Requires a valid JWT token in the Authorization header.

**Response:**
```json
{
  "plan": {
    "type": "standard",
    "start_date": "2023-10-01T15:30:45Z",
    "expiry_date": "2023-10-31T15:30:45Z",
    "is_active": true
  },
  "daily_limits": {
    "paths": 10,
    "cards": 50
  },
  "daily_usage": {
    "date": "2023-10-30",
    "paths": {
      "count": 2,
      "remaining": 8,
      "limit_reached": false
    },
    "cards": {
      "count": 15,
      "remaining": 35,
      "limit_reached": false
    }
  }
}
```

**Frontend Usage Example:**
```javascript
// React example using axios
import axios from 'axios';

const fetchSubscriptionInfo = async () => {
  try {
    const response = await axios.get('/api/subscription', {
      headers: {
        'Authorization': `Bearer ${jwtToken}`
      }
    });
    
    const subscriptionData = response.data;
    
    // Update UI with subscription information
    setSubscriptionType(subscriptionData.plan.type);
    setSubscriptionStartDate(subscriptionData.plan.start_date);
    setSubscriptionExpiryDate(subscriptionData.plan.expiry_date);
    setSubscriptionActive(subscriptionData.plan.is_active);
    
    setDailyLimits(subscriptionData.daily_limits);
    setDailyUsage(subscriptionData.daily_usage);
    
    // Calculate and display progress
    const pathsProgress = (subscriptionData.daily_usage.paths.count / subscriptionData.daily_limits.paths) * 100;
    const cardsProgress = (subscriptionData.daily_usage.cards.count / subscriptionData.daily_limits.cards) * 100;
    
    setPathsProgressBar(pathsProgress);
    setCardsProgressBar(cardsProgress);
    
    // Check if subscription is expiring soon (within 5 days)
    if (subscriptionData.plan.is_active && subscriptionData.plan.type !== 'free') {
      const expiryDate = new Date(subscriptionData.plan.expiry_date);
      const today = new Date();
      const daysUntilExpiry = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));
      
      if (daysUntilExpiry <= 5) {
        showNotification(`Your subscription expires in ${daysUntilExpiry} days. Please renew to avoid service interruption.`);
      }
    }
  } catch (error) {
    console.error('Error fetching subscription info:', error);
  }
};
```

### Update Subscription

**Endpoint:**
```
PUT /api/subscription
```

**Authentication:**
Requires a valid JWT token in the Authorization header.

**Request Body:**
```json
{
  "subscription_type": "standard",
  "promotion_code": "zeroai#0430",
  "expiry_days": 30
}
```

**Response:**
```json
{
  "id": 123,
  "email": "user@example.com",
  "username": "example_user",
  "subscription_type": "standard",
  "subscription_start_date": "2023-10-01T15:30:45Z",
  "subscription_expiry_date": "2023-10-31T15:30:45Z",
  "full_name": "Example User",
  "profile_picture": "https://example.com/profile.jpg",
  "is_active": true,
  "oauth_provider": null,
  "is_superuser": false,
  "created_at": "2023-01-15T08:30:00Z"
}
```

**Frontend Usage Example:**
```javascript
// React example using fetch
const upgradeSubscription = async (subscriptionType, promoCode = null, expiryDays = 30) => {
  try {
    const requestBody = {
      subscription_type: subscriptionType,
      expiry_days: expiryDays
    };
    
    if (promoCode) {
      requestBody.promotion_code = promoCode;
    }
    
    const response = await fetch('/api/subscription', {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to update subscription');
    }
    
    const updatedUser = await response.json();
    
    // Update UI with new subscription information
    setSubscriptionType(updatedUser.subscription_type);
    setSubscriptionStartDate(updatedUser.subscription_start_date);
    setSubscriptionExpiryDate(updatedUser.subscription_expiry_date);
    
    // Format expiry date for display
    const expiryDate = new Date(updatedUser.subscription_expiry_date);
    const formattedExpiry = expiryDate.toLocaleDateString();
    
    showNotification(`Successfully upgraded to ${updatedUser.subscription_type} subscription! Valid until ${formattedExpiry}`);
    
    // Refresh usage and limits
    fetchSubscriptionInfo();
  } catch (error) {
    console.error('Error upgrading subscription:', error);
    showErrorNotification(error.message);
  }
};
```

## Error Handling

When implementing subscription-related features, be prepared to handle these common error scenarios:

### Daily Limit Reached
**Status Code:** 403 Forbidden
```json
{
  "detail": "Daily limit reached for learning paths. Your limit is 3 paths per day."
}
```

### Invalid Promotion Code
**Status Code:** 400 Bad Request
```json
{
  "detail": "Invalid promotion code"
}
```

### Unauthorized Access
**Status Code:** 401 Unauthorized
```json
{
  "detail": "Authentication required"
}
```

### Expired Subscription
**Status Code:** 403 Forbidden
```json
{
  "detail": "Your subscription has expired. Please renew to continue using premium features."
}
```

## Frontend Implementation Recommendations

1. **Check Limits Before Actions:**
   Before allowing users to generate paths or cards, check if they've reached their daily limits and update the UI accordingly.

   ```javascript
   // Example for disabling a "Generate Path" button
   useEffect(() => {
     fetchSubscriptionInfo().then(data => {
       if (data.daily_usage.paths.limit_reached) {
         setGenerateButtonDisabled(true);
         setLimitMessage(`Daily limit reached. You can generate more paths tomorrow.`);
       }
       
       // Also check if subscription is active
       if (data.plan.type !== 'free' && !data.plan.is_active) {
         setSubscriptionExpiredMessage(`Your subscription has expired on ${new Date(data.plan.expiry_date).toLocaleDateString()}`);
         showRenewSubscriptionButton(true);
       }
     });
   }, []);
   ```

2. **Display Remaining Resources:**
   Show users how many paths and cards they can still generate today.

   ```jsx
   <div className="usage-info">
     <p>Paths remaining today: {pathsRemaining} / {pathsLimit}</p>
     <p>Cards remaining today: {cardsRemaining} / {cardsLimit}</p>
   </div>
   ```

3. **Progress Visualization:**
   Display visual indicators of usage limits.

   ```jsx
   <div className="progress-container">
     <label>Paths Usage</label>
     <progress value={pathsUsed} max={pathsLimit}></progress>
     <span>{pathsRemaining} remaining</span>
   </div>
   ```

4. **Subscription Upgrade Prompts:**
   When a user reaches their limit, offer subscription upgrade options.

   ```jsx
   {pathsRemaining <= 0 && (
     <div className="upgrade-prompt">
       <p>You've reached your daily paths limit.</p>
       <button onClick={() => showUpgradeModal()}>
         Upgrade Subscription
       </button>
     </div>
   )}
   ```

5. **Subscription Status Display:**
   Show subscription status and expiration information.

   ```jsx
   <div className="subscription-status">
     <h3>Your Subscription</h3>
     <p>Current Plan: <strong>{subscriptionType}</strong></p>
     
     {subscriptionType !== 'free' && (
       <>
         <p>Start Date: {new Date(subscriptionStartDate).toLocaleDateString()}</p>
         <p>Expiry Date: {new Date(subscriptionExpiryDate).toLocaleDateString()}</p>
         <p>Status: {isSubscriptionActive ? 
           <span className="status-active">Active</span> : 
           <span className="status-expired">Expired</span>
         }</p>
         
         {!isSubscriptionActive && (
           <button className="renew-button" onClick={handleRenewSubscription}>
             Renew Subscription
           </button>
         )}
         
         {isSubscriptionActive && daysUntilExpiry <= 5 && (
           <div className="expiry-warning">
             Your subscription expires in {daysUntilExpiry} days
             <button onClick={handleRenewSubscription}>Renew Now</button>
           </div>
         )}
       </>
     )}
   </div>
   ```

6. **Subscription Duration Selection:**
   Allow users to select subscription duration when upgrading.

   ```jsx
   <div className="subscription-duration">
     <h4>Choose Subscription Duration</h4>
     <select value={durationDays} onChange={(e) => setDurationDays(parseInt(e.target.value))}>
       <option value="30">1 Month (30 days)</option>
       <option value="90">3 Months (90 days)</option>
       <option value="180">6 Months (180 days)</option>
       <option value="365">1 Year (365 days)</option>
     </select>
     
     <button onClick={() => upgradeSubscription(selectedPlan, promoCode, durationDays)}>
       Complete Upgrade
     </button>
   </div>
   ```

## Available Promotion Codes

The system supports promotional codes that automatically upgrade users to specific tiers:

- **Standard Tier Upgrade**: `zeroai#0430`
  - Automatically upgrades the user to the standard subscription
  - Increases daily limits to 10 learning paths and 50 cards
  - **Limited redemptions**: First 200 users only

- **Premium Tier Upgrade**: `zeroultra#2025`
  - Automatically upgrades the user to the premium subscription 
  - Increases daily limits to 100 learning paths and 500 cards
  - **Limited redemptions**: First 100 users only

### How Promotion Codes Work

1. **Automatic Tier Determination**:
   - Users don't need to specify which tier they want to upgrade to
   - The system automatically determines the appropriate tier based on the code
   - Each code is mapped to a specific subscription tier in the backend

2. **Backend Implementation**:
   - Promotion codes are stored in a database table with usage tracking
   - Each code has a defined redemption limit (200 for standard, 100 for premium)
   - The system increments a counter each time a code is successfully used
   - When a code reaches its redemption limit, it can no longer be used
   - If the user applies a code that would downgrade their subscription, the higher tier is maintained

3. **Redemption Process**:
   ```javascript
   // Example of using just a promotion code without specifying tier
   const applyPromotionCode = async (promoCode) => {
     try {
       // Only the promotion code is required
       const requestBody = {
         promotion_code: promoCode
       };
       
       const response = await fetch('/api/subscription', {
         method: 'PUT',
         headers: {
           'Authorization': `Bearer ${jwtToken}`,
           'Content-Type': 'application/json'
         },
         body: JSON.stringify(requestBody)
       });
       
       if (!response.ok) {
         const errorData = await response.json();
         throw new Error(errorData.detail || 'Failed to apply promotion code');
       }
       
       const updatedUser = await response.json();
       
       // The backend automatically determines which tier to assign
       showNotification(`Successfully upgraded to ${updatedUser.subscription_type} subscription using promo code!`);
       
       // Refresh subscription information
       fetchSubscriptionInfo();
     } catch (error) {
       console.error('Error applying promotion code:', error);
       showErrorNotification(error.message);
     }
   };
   ```

4. **Code Redemption UI**:
   ```jsx
   <div className="promo-code-form">
     <h3>Have a Promotion Code?</h3>
     <input 
       type="text" 
       value={promoCode} 
       onChange={(e) => setPromoCode(e.target.value)}
       placeholder="Enter your code here" 
     />
     <button 
       onClick={() => applyPromotionCode(promoCode)}
       disabled={!promoCode.trim()}
     >
       Apply Code
     </button>
   </div>
   ```

5. **Possible Error Messages**:

   - **Invalid Code**:
     ```json
     {
       "detail": "Invalid promotion code"
     }
     ```

   - **Code Already Used**:
     ```json
     {
       "detail": "This promotion code has already been used with your account"
     }
     ```

   - **Code Redemption Limit Reached**:
     ```json
     {
       "detail": "This promotion code has reached its maximum number of redemptions"
     }
     ```

## API Implementation Details

The subscription system is implemented in the following files:

- `app/models.py`: Contains the User model with subscription fields (subscription_type, subscription_start_date, subscription_expiry_date) and the PromotionCodeUsage model for tracking code redemptions
- `app/users/crud.py`: Includes functions for managing subscriptions, checking daily limits, and handling promotion code redemptions
- `app/users/routes.py`: Provides endpoints for subscription management and info
- `app/user_daily_usage/crud.py`: Handles daily usage tracking

### Database Schema

The system uses the following database tables for subscription management:

1. **users**: Contains subscription-related fields
   - `subscription_type`: The user's current plan (free, standard, premium)
   - `subscription_start_date`: When the subscription began
   - `subscription_expiry_date`: When the subscription will expire

2. **user_daily_usage**: Tracks daily consumption of resources
   - `paths_generated`: Number of learning paths generated today
   - `cards_generated`: Number of cards generated today
   - `paths_daily_limit`: Daily limit based on subscription tier
   - `cards_daily_limit`: Daily limit based on subscription tier

3. **promotion_code_usage**: Tracks promotion code redemptions
   - `code`: The promotion code string
   - `tier`: The subscription tier this code provides
   - `total_limit`: Maximum number of times this code can be redeemed
   - `times_used`: Number of times the code has been redeemed

## Support

If users encounter issues with their subscription or need assistance with upgrades, they can contact support at support@zeroai.example.com.
