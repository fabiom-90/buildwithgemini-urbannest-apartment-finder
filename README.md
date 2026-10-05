# UrbanNest Apartment Finder 🏢✨

An AI-powered real estate assistant built with Google Agent Development Kit (ADK), Google Cloud Platform services, and Agent-to-User Interface (A2UI) support. UrbanNest helps users search for apartments, explore floor plans, visualize virtual room staging, generate short video tours, calculate move-in affordability, and discover neighborhood amenities.

![UrbanNest Demo](demo.gif)

---

## 🚀 Overview

UrbanNest Apartment Finder integrates multimodal AI models, real-time database queries, long-term session memory, and custom UI components into a chat interface.

### Implemented Features & Google Cloud Services

The agent implementation in `app/` leverages the following Google Cloud and ADK capabilities:

- **Firestore Database Integration**: Real-time querying, filtering, and retrieval of apartment listings (e.g. by price, bedrooms, neighborhood, pet policy, and move-in date) stored in Google Cloud Firestore.
- **Vertex AI Memory Bank Service**: Cross-session long-term memory via `VertexAiMemoryBankService` to record user preferences, pet ownership, health constraints, and allergies across conversations.
- **Multimodal AI Media Generation**:
  - **Virtual Room Staging**: AI room concepts generated using `gemini-2.5-flash-image`.
  - **2D Architectural Floor Plans**: Architectural blueprint renderings generated using `gemini-3.1-flash-lite-image`.
  - **Virtual Video Tours**: Short 5-second video walkthroughs generated using Google's Omni model (`gemini-omni-flash-preview`).
- **Google Cloud Storage (GCS)**: Direct storage and public media hosting for generated floor plans, room staging concepts, and virtual video tour files.
- **Google Maps & Places Services**:
  - **Geocoding & ZIP Code Lookup**: Converting street addresses and ZIP codes into geographic coordinates.
  - **Nearby Amenities**: Searching for local schools, transit hubs, parks, grocery stores, and restaurants near listings.
- **Agent Engine Sandbox Code Executor**: Isolated Python execution environment (`AgentEngineSandboxCodeExecutor`) for accurate rent affordability ratios and upfront move-in cash calculations.
- **Agent-to-User Interface (A2UI)**: Structured UI rendering (Cards, Columns, Rows, Text, Images) enabling visual display of listing results in the chat interface.

---

## 🛠️ Project Structure

```
urbannest-apartment-finder/
├── app/
│   ├── agent.py               # Core ADK agent definition, tools, and callbacks
│   ├── a2ui_utils.py          # A2UI schema manager and response callbacks
│   ├── __init__.py            # Package initialization
│   └── database/              # Firestore seed and schema helpers
├── frontend/
│   ├── main.py                # FastAPI proxy server for agent-to-browser streaming
│   ├── requirements.txt       # Frontend dependencies
│   ├── Dockerfile             # Container definition for frontend service
│   └── static/
│       └── index.html         # Modern web chat UI with interactive image lightbox
├── agents-cli-manifest.yaml   # Agent deployment manifest
├── deployment_metadata.json   # Deployed Agent Runtime metadata
├── demo.gif                   # Automated demo video recording
└── README.md                  # Project documentation
```

---

## 📋 Planned / Future Enhancements

The following features were outlined in initial design concepts but are **planned, not yet implemented**:

- [ ] **Direct Lease Booking & Agent Scheduling**: Calendar booking integration for in-person apartment viewings.
- [ ] **Multi-party Co-Renter Chat**: Shared chat rooms for roommates searching for apartments together.
- [ ] **Credit Check & Application Submission**: Secure document processing for tenant credit verification.

---

## 💻 Local Setup & Execution

Follow these steps to run the frontend and backend locally:

### Prerequisites

- Python 3.11+
- Google Cloud SDK (`gcloud`) configured with an active GCP project
- Google Cloud credentials (`gcloud auth application-default login`)

### 1. Environment Setup

Copy or set the necessary environment variables:

```bash
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-east1"
export AGENT_ENGINE_RESOURCE_NAME="projects/YOUR_PROJECT/locations/us-east1/reasoningEngines/YOUR_ENGINE_ID"
export AGENT_DIRECTORY="app"
```

### 2. Frontend Installation & Running

Navigate to the `frontend/` directory, install dependencies, and start the FastAPI proxy server:

```bash
cd frontend
pip install -r requirements.txt
python main.py
```

Once running, open your web browser and navigate to the port output by the server (default port `8080`).

### 3. Deploying the Agent

To deploy or update the agent on Google Cloud Agent Runtime:

```bash
agents-cli deploy --update-env-vars GOOGLE_MAPS_API_KEY=YOUR_MAPS_KEY --no-confirm-project
```
