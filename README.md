# NourishAI

*Hackathon Project – Social Good Track (HopHacks 2025, sponsored by Bloomberg)*

Nourish AI is a voice + web-powered platform designed to improve food accessibility by connecting people in need with nearby food banks. Built in just 36 hours, this project leverages AI, location intelligence, and secure payments to support philanthropic goals.


## 🚀 The Mission (In a Nutshell)
Food insecurity is a massive challenge, but local communities have the power to solve it. The problem is a gap in information—people want to help, but don't know what is needed, where to go, or how to contribute effectively.

NourishAI bridges that gap. We built a smart, intuitive platform that makes finding food assistance and donating resources as easy as sending a text message. No more guessing games, no more wasted food—just direct, impactful support.


## 🔥 Core Features

We packed a ton of functionality into this app over the hackathon weekend:

**📍 Interactive Pantry Finder:** Utilizes the Google Maps API to display a map of nearby food pantries, markets, and shopping partners. Users can instantly see what's available in their area.

**🤖 AI-Powered Food Donations:** This is our secret sauce! A user can simply state what they want to donate (e.g., "I have 5 cans of soup and a box of pasta"). The Gemini API parses this natural language into a structured update that gets logged for the selected pantry.

**⚡️ Real-Time Pantry Updates:** Pantries have a "live" status showing the most recent food donations. This helps donors give what's actually needed and reduces waste. The logic is simple but effective: updates are merged for 48 hours before being replaced to keep info fresh.

**💳 Secure Monetary Donations:** We integrated Stripe to provide a secure, seamless payment gateway. Supporters can donate money directly to the cause with just a few clicks, without our app ever touching sensitive financial data.

**☁️ Cloud-Powered & Scalable:** The entire application is powered by a SQLite Cloud database and is live on the web, hosted via Render.com.


## 🛠️ Tech Stack & Architecture
This project was built with a fast, modern, and scalable stack perfect for a rapid hackathon build.

**Backend:** Flask

**Database:** SQLite Cloud (via sqlitecloud and SQLAlchemy)

**Hosting:** Render.com

**Key APIs:**

Google Maps API: For geocoding and mapping food pantry locations.

Google Gemini API: For natural language processing of food donation inputs.

Stripe API: For processing secure monetary donations.

SQLite Cloud: For our database connection.


## ⚙️ Local Setup & Installation
Want to run this project locally? Let's get you set up in 5 minutes.

1. Clone the Repository

    git clone https://github.com/samiahmed23/call-for-meal

    cd NourishAI

2. Set Up a Virtual Environment
    ## For Windows
    python -m venv venv

    venv\Scripts\activate

    ## For macOS/Linux
    python3 -m venv venv

    source venv/bin/activate

3. Install Dependencies

    We've listed everything you need in requirements.txt.

    *pip install -r requirements.txt*

4. CRITICAL: Configure Your API Keys

    **This is the most important step.** Our app relies on external services.

    Create a file named *.env* in the root of the project directory. Copy the contents of .env.example (if one exists) or create it from scratch.

    Your .env file must look like this:

    ## Get from Google Cloud Console (enable Geocoding API)
    GOOGLE_MAPS_API_KEY="AIza..."

    ## Get from Google AI Studio
    GEMINI_API_KEY="AIza..."

    ## Get from your Stripe Dashboard (use test keys!)
    STRIPE_SECRET_KEY="sk_test_..."
    STRIPE_PUBLIC_KEY="pk_test_..."

    ## Get from your SQLite Cloud Dashboard
    SQLITECLOUD_CONNECTION_STRING="sqlitecloud://user:password@hostname.sqlite.cloud:port/database"


    **Where to Get Your Keys ?**

    *Google Maps & Gemini:* Go to Google Cloud Console. You will need to create a project, enable the "Geocoding API" for maps, and get a Gemini key from the Google AI Studio.

    *Stripe:* Create a free account at Stripe.com. Your test keys (pk_test and sk_test) are available in the "Developers" section of the dashboard.

    *SQLite Cloud:* Sign up at SQLite.cloud and create a new database. The full connection string is provided on your database dashboard.

5. Run the Application

flask run

Navigate to http://127.0.0.1:5000/ in your browser and you should be live!

Hosted website: https://call-for-meal.onrender.com/

## 🚀 What's Next? (Future Ideas)

This was an amazing hackathon build, but we're just getting started. Here's where we could take NourishAI next:

**Live Inventory Management:** Allow pantries to log in and manage a simple inventory, giving donors an even clearer picture of their needs.

**SMS Notifications:** Alert subscribed users when a local pantry has an urgent need.

**Gamification:** Create a points system for donations to encourage community engagement.

Built with ❤️ for the community. Let's nourish it together.
