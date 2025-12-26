from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import pandas as pd
import os
import urllib.parse
from dotenv import load_dotenv

# --- 1. SETUP & SECURITY ---
load_dotenv()  # Load variables from .env file

app = Flask(__name__)
CORS(app)  # Allow Frontend to connect

# Get credentials safely
password = os.getenv("MONGO_PASS")
username = "admin"
cluster = "cluster0.uhywodh.mongodb.net"

if not password:
    print("❌ Error: MONGO_PASS not found in .env file.")
    exit()

# Encode credentials
escaped_username = urllib.parse.quote_plus(username)
escaped_password = urllib.parse.quote_plus(password)
# Use the simpler +srv string now that your network is working
connection_string = f"mongodb+srv://{escaped_username}:{escaped_password}@{cluster}/?retryWrites=true&w=majority"
# --- 2.1 SPECIES FACT DATA (STATIC REFERENCE DATA) ---

SPECIES_FACTS = {
    "Alligator mississippiensis": {
        "common_name": "American Alligator",
        "primary_threats": ["Illegal skin trade", "Habitat loss"],
        "poaching_reason": "is targeted for its high-grade hide, which is prized in the fashion industry for luxury 'classic scale' leather goods. Illegal harvesting often occurs to bypass strict state-monitored tagging programs and harvest quotas."
    },
    "Crocodylus niloticus": {
        "common_name": "Nile Crocodile",
        "primary_threats": ["Poaching", "Human-wildlife conflict"],
        "poaching_reason": "is hunted both for its skin and for meat in local markets. Because it is often involved in human-wildlife conflict, illegal killing is frequently disguised as 'problem animal control' to enter the black market."
    },
    "Crocodylus porosus": {
        "common_name": "Saltwater Crocodile",
        "primary_threats": ["Illegal hunting", "Habitat degradation"],
        "poaching_reason": "possesses the most valuable crocodilian skin in the world due to its small, uniform scale pattern. Poachers target wild populations in Southeast Asia to satisfy the extreme demand from high-end European fashion houses."
    },
    "Python bivittatus": {
        "common_name": "Burmese Python",
        "primary_threats": ["Skin trade", "Pet trade"],
        "poaching_reason": "is exploited for the luxury leather market and the exotic pet trade. Large wild specimens are specifically targeted as their skins provide more surface area for leather production without the cost of captive rearing."
    },
    "Python reticulatus": {
        "common_name": "Reticulated Python",
        "primary_threats": ["Commercial hunting", "Illegal trade"],
        "poaching_reason": "is the world's longest snake, making its skin highly profitable for large leather items. It is often poached in massive numbers across Indonesia and Malaysia, frequently exceeding legal CITES export limits."
    },
    "Varanus salvator": {
        "common_name": "Asian Water Monitor",
        "primary_threats": ["Leather trade", "Habitat loss"],
        "poaching_reason": "is the second-most traded monitor lizard in the world. Its skin is exceptionally durable and flexible, making it the primary choice for illegal watchband and small accessory manufacturing."
    }
}

# Connect to DB
try:
    # Add this argument to bypass SSL certificate verification
    client = MongoClient(connection_string, tlsAllowInvalidCertificates=True)
    db = client["wildlife_db"]
    # Quick test
    client.admin.command('ping')
    print("✅ Connected to MongoDB Atlas!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    exit()

# --- 2. PRE-CALCULATE GLOBAL MEANS ---
# We need the average of ALL animals to compare against the specific animal.
# We do this once when the server starts to save time.
print("📊 Calculating global statistics...")
try:
    # Fetch all feature data to calculate averages
    all_features = list(db.features.find({}, {"_id": 0}))
    if all_features:
        df_global = pd.DataFrame(all_features)
        # Calculate mean of numeric columns only
        GLOBAL_MEANS = df_global.mean(numeric_only=True).to_dict()
        print("✅ Global means calculated.")
    else:
        GLOBAL_MEANS = {}
        print("⚠️ Warning: No data in features collection.")
except Exception as e:
    print(f"❌ Error calculating means: {e}")
    GLOBAL_MEANS = {}


# --- 3. HELPER FUNCTION ---
def explain_risk(taxon, country, profile_data, means):
    reasons = []
    
    # Compare specific animal data against Global Means
    if profile_data.get('export_qty_log', 0) > means.get('export_qty_log', 0):
        reasons.append("higher-than-average export volume")
    if profile_data.get('num_trade_events', 0) > means.get('num_trade_events', 0):
        reasons.append("frequent export transactions")
    if profile_data.get('source_risk', 0) > means.get('source_risk', 0):
        reasons.append("predominantly wild-sourced specimens")
    if profile_data.get('live_trade_ratio', 0) > means.get('live_trade_ratio', 0):
        reasons.append("significant live animal trade")
    if profile_data.get('appendix_risk', 0) >= 2:
        reasons.append("higher CITES protection status")

    if not reasons:
        return "Risk is moderate due to average trade behavior."
    return "Risk is elevated due to " + ", ".join(reasons) + "."


# --- 4. API ENDPOINT ---
@app.route('/get_animal_data', methods=['GET'])
@app.route('/get_animal_data', methods=['GET'])
def get_animal_data():
    taxon = request.args.get('taxon')
    if not taxon:
        return jsonify({"error": "No taxon provided"}), 400

    # A. DB Lookup (Case-insensitive Regex)
    prediction = db.predictions.find_one({"Taxon": {"$regex": f"^{taxon}$", "$options": "i"}}, {"_id": 0})
    if not prediction:
        return jsonify({"error": "Species not found"}), 404

    # B. Dictionary Lookup (Case-insensitive fix)
    # This searches the dictionary keys by converting them all to lowercase
    facts = next((v for k, v in SPECIES_FACTS.items() if k.lower() == taxon.lower().strip()), None)

    # C. Build Species Specific Reason
    if facts and "poaching_reason" in facts:
        why_text = f"This species {facts['poaching_reason']} "
    else:
        # If this text appears, it means the name isn't in your SPECIES_FACTS dictionary
        why_text = "Analysis indicates risk is driven by international trade demand. "

    # D. Build Trade Behavior Reason
    features_list = list(db.features.find({"Taxon": {"$regex": f"^{taxon}$", "$options": "i"}}, {"_id": 0}))
    likely_country = prediction.get('likely_poaching_country')
    specific_profile = next((item for item in features_list if item["Exporter"] == likely_country), None)
    
    how_text = ""
    if specific_profile:
        how_text = explain_risk(taxon, likely_country, specific_profile, GLOBAL_MEANS)

    return jsonify({
        "basic_info": prediction,
        "heatmap_data": features_list, 
        "risk_explanation": why_text + how_text
    })
@app.route('/get_species_facts', methods=['GET'])
def get_species_facts():
    taxon = request.args.get('taxon')

    if not taxon:
        return jsonify({"error": "No taxon provided"}), 400

    # This matches the "safe" lookup you used in the other route
    facts = next((v for k, v in SPECIES_FACTS.items() if k.lower() == taxon.lower().strip()), None)

    if not facts:
        return jsonify({"error": "Species facts not found"}), 404

    return jsonify(facts)
if __name__ == '__main__':
    # We set use_reloader=False to prevent double-connection attempts to MongoDB
    app.run(debug=True, use_reloader=False, port=5000)