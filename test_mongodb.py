"""Test MongoDB Atlas connection and data storage."""

import os
from dotenv import load_dotenv

# Load env
load_dotenv()

print("=" * 60)
print("MPRG MongoDB Atlas Connection Test")
print("=" * 60)

# Check env
mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    print("❌ MONGODB_URI not set in .env")
    exit(1)
    
# Mask the URI for display
masked = mongo_uri[:20] + "..." + mongo_uri[-20:] if len(mongo_uri) > 50 else mongo_uri
print(f"✅ MONGODB_URI found: {masked}")

# Try connection
print("\n📡 Connecting to MongoDB Atlas...")

try:
    from pymongo import MongoClient
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    
    # Force connection
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB Atlas!")
    
    # Get database
    db = client.mprg
    print(f"📊 Using database: 'mprg'")
    
    # List collections
    collections = db.list_collection_names()
    print(f"📁 Existing collections: {collections}")
    
    # Count documents in each collection
    for coll_name in ['agent_outputs', 'reasoning_traces', 'reasoning_families', 'robustness_results']:
        coll = db[coll_name]
        count = coll.count_documents({})
        print(f"   - {coll_name}: {count} documents")
    
    # Sample data from robustness_results if any
    if db.robustness_results.count_documents({}) > 0:
        print("\n📋 Most recent robustness result:")
        latest = db.robustness_results.find_one(sort=[("created_at", -1)])
        if latest:
            print(f"   Task ID: {latest.get('task_id')}")
            print(f"   Score: {latest.get('robustness_score')}")
            print(f"   Families: {latest.get('distinct_families')}")
            print(f"   Gate: {latest.get('gate_decision')}")
    else:
        print("\n⚠️  No results yet - run an analysis to populate data")
        
    print("\n" + "=" * 60)
    print("MongoDB Atlas is working! 🎉")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)
