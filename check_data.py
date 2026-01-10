"""Check MongoDB data after analysis."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv('MONGODB_URI'))
db = client.mprg

print('=== MongoDB Atlas Data ===')
for coll in ['agent_outputs', 'reasoning_traces', 'robustness_results']:
    count = db[coll].count_documents({})
    print(f'{coll}: {count} documents')
    
if db.robustness_results.count_documents({}) > 0:
    latest = db.robustness_results.find_one(sort=[('created_at', -1)])
    print('\nLatest Result:')
    task = latest.get('task_prompt', '')[:50]
    print(f'  Task: {task}')
    print(f'  Score: {latest.get("robustness_score")}')
    print(f'  Families: {latest.get("distinct_families")}')
    print(f'  Gate: {latest.get("gate_decision")}')
else:
    print('\nNo results stored yet')
