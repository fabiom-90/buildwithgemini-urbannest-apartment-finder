from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-8fe52a72cc9e"
COLLECTION_NAME = "apartment_listings"

db = firestore.Client(project=PROJECT_ID)

listings = [
    {
        "id": "apt_101",
        "title": "Sunlit Modern 1BR in SoMa",
        "neighborhood": "SoMa",
        "city": "San Francisco",
        "price": 3200,
        "bedrooms": 1,
        "bathrooms": 1.0,
        "sqft": 750,
        "pets_allowed": True,
        "amenities": ["in-unit laundry", "balcony", "gym", "elevator"],
        "description": "Floor-to-ceiling windows with panoramic city views, modern kitchen appliances, and concrete polished floors.",
        "available_date": "2026-11-01"
    },
    {
        "id": "apt_102",
        "title": "Spacious 2BR Loft in Mission District",
        "neighborhood": "Mission District",
        "city": "San Francisco",
        "price": 4100,
        "bedrooms": 2,
        "bathrooms": 2.0,
        "sqft": 1150,
        "pets_allowed": True,
        "amenities": ["parking", "private patio", "in-unit laundry", "dishwasher"],
        "description": "Converted warehouse loft featuring exposed brick, high ceilings, gourmet gas range, and attached garage parking.",
        "available_date": "2026-10-15"
    },
    {
        "id": "apt_103",
        "title": "Cozy Garden Studio near Golden Gate Park",
        "neighborhood": "Richmond",
        "city": "San Francisco",
        "price": 2400,
        "bedrooms": 0,
        "bathrooms": 1.0,
        "sqft": 520,
        "pets_allowed": False,
        "amenities": ["shared garden", "storage unit", "hardwood floors"],
        "description": "Quiet ground-floor studio steps away from Golden Gate Park with updated kitchen and garden access.",
        "available_date": "2026-10-20"
    },
    {
        "id": "apt_104",
        "title": "Luxury 3BR Penthouse in Marina",
        "neighborhood": "Marina",
        "city": "San Francisco",
        "price": 6500,
        "bedrooms": 3,
        "bathrooms": 2.5,
        "sqft": 1800,
        "pets_allowed": True,
        "amenities": ["roof deck", "parking", "wine fridge", "in-unit laundry", "doorman"],
        "description": "Top-floor residence with bay and Golden Gate bridge views, private rooftop terrace, and concierge services.",
        "available_date": "2026-11-15"
    }
]

def seed_database():
    print(f"Seeding Firestore collection '{COLLECTION_NAME}' in project '{PROJECT_ID}'...")
    for item in listings:
        doc_ref = db.collection(COLLECTION_NAME).document(item["id"])
        doc_ref.set(item)
        print(f"  ✓ Added listing: {item['id']} - {item['title']}")
    print("Firestore database seeded successfully!")

if __name__ == "__main__":
    seed_database()
