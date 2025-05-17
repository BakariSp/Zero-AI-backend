🧩 Goal
Enable users to:

Use the app without logging in (via guest accounts).

Persist their data via anonymous IDs.

Seamlessly upgrade to real accounts later, migrating their data.

Avoid account duplication when existing users forget to log in.

✅ 1. Database Schema Changes
users table
Add fields:

sql
Copy
Edit
ALTER TABLE users
ADD COLUMN is_guest BOOLEAN DEFAULT FALSE,
ADD COLUMN merged_into_user_id INT NULL,
ADD COLUMN last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP;
Guest users: is_guest = TRUE, merged_into_user_id = NULL
Merged guest users: merged_into_user_id = <real_user_id>

✅ 2. API Changes
a. POST /auth/guest
Create a new guest account:

python
Copy
Edit
@app.post("/auth/guest")
def create_guest_user(db: Session = Depends(get_db)):
    guest_user = User(
        is_guest=True,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow()
    )
    db.add(guest_user)
    db.commit()
    db.refresh(guest_user)
    token = generate_jwt(user_id=guest_user.id, is_guest=True)
    return {"user_id": guest_user.id, "token": token}
Use short-lived JWT or include a flag like is_guest in the token.

Store this token or ID in localStorage on the frontend.

b. POST /auth/merge
Merge guest account into a registered one:

python
Copy
Edit
@app.post("/auth/merge")
def merge_accounts(guest_id: int, real_user_id: int, db: Session = Depends(get_db)):
    # Validate both exist
    guest = db.query(User).filter_by(id=guest_id, is_guest=True).first()
    real_user = db.query(User).filter_by(id=real_user_id, is_guest=False).first()

    if not guest or not real_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Migrate learning paths, progress, etc.
    db.query(LearningPath).filter_by(user_id=guest.id).update({"user_id": real_user.id})
    db.query(KeywordProgress).filter_by(user_id=guest.id).update({"user_id": real_user.id})
    
    # Mark guest as merged
    guest.merged_into_user_id = real_user.id
    db.commit()
    return {"status": "merged"}
c. Middleware / Dependency Enhancement
Modify your existing get_current_user() dependency to also accept guest tokens:

python
Copy
Edit
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_jwt(token)
    user = db.query(User).filter_by(id=payload["user_id"]).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.merged_into_user_id:
        user = db.query(User).filter_by(id=user.merged_into_user_id).first()

    return user
✅ 3. Data Cleanup Cron Job
Add a scheduled job (e.g. via Celery or Azure Scheduler) to remove old unused guest accounts:

sql
Copy
Edit
DELETE FROM users
WHERE is_guest = TRUE
  AND merged_into_user_id IS NULL
  AND last_active_at < NOW() - INTERVAL 30 DAY;
✅ 4. Optional: Analytics & Conversion Tracking
Track guest → user conversion rates:

Add source column to user: e.g., "organic", "try-demo", "path-gen"

Log guest_id on sign-up flow for attribution

📦 Summary
Change	Type	Purpose
is_guest, merged_into_user_id in users	DB	Identify temporary users
POST /auth/guest	API	Enable instant trial
POST /auth/merge	API	Migrate progress
Enhance get_current_user()	Code	Support guest tokens
Cleanup script	Ops	Prevent database bloat