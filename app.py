from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import pandas as pd
import os
import urllib.parse
from dotenv import load_dotenv

# --- 1. SETUP & SECURITY ---
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# MongoDB Configuration
username = "admin"
password = os.getenv("MONGO_PASS")
cluster = "cluster0.uhywodh.mongodb.net"

if not password:
    print("❌ Error: MONGO_PASS not found in .env file.")
    exit()

escaped_username = urllib.parse.quote_plus(username)
escaped_password = urllib.parse.quote_plus(password)
connection_string = (
    f"mongodb+srv://{escaped_username}:{escaped_password}@{cluster}/"
    "?retryWrites=true&w=majority"
)

# Database Connection
try:
    client = MongoClient(
        connection_string,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000
    )
    db = client["wildlife_db"]
    client.admin.command("ping")
    print("✅ Connected to MongoDB Atlas!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    exit()

# --- 2. PRE-CALCULATE GLOBAL MEANS ---
try:
    all_features = list(db.features.find({}, {"_id": 0}))
    if all_features:
        df_global = pd.DataFrame(all_features)
        GLOBAL_MEANS = df_global.mean(numeric_only=True).to_dict()
        print("✅ Global means calculated.")
    else:
        GLOBAL_MEANS = {}
        print("⚠️ No feature data found.")
except Exception as e:
    print(f"❌ Mean calculation error: {e}")
    GLOBAL_MEANS = {}

# --- 3. STATIC SPECIES FACTS (normalized to lowercase keys) ---
SPECIES_FACTS = {
    "alligator mississippiensis": {
        "common_name": "American Alligator",
        "poaching_reason": "is targeted for its high-grade hide, prized in luxury leather goods."
    },
    "crocodylus niloticus": {
        "common_name": "Nile Crocodile",
        "poaching_reason": "is hunted for both skin and meat in local and international markets."
    },
    "crocodylus porosus": {
        "common_name": "Saltwater Crocodile",
        "poaching_reason": "possesses the most valuable crocodilian skin due to its small, uniform scale pattern."
    },
    "python bivittatus": {
        "common_name": "Burmese Python",
        "poaching_reason": "is exploited for the luxury leather market and exotic pet trade."
    },
    "python reticulatus": {
        "common_name": "Reticulated Python",
        "poaching_reason": "is the world's longest snake, making its skin highly profitable for large leather items."
    },
    "varanus salvator": {
        "common_name": "Asian Water Monitor",
        "poaching_reason": "is targeted for its exceptionally durable and flexible skin, used in watchbands."
    }
}

# --- 4. HELPER FUNCTION ---
def explain_risk(profile, means):
    if not profile:
        return ""

    reasons = []

    if profile.get("export_qty_log", 0) > means.get("export_qty_log", 0):
        reasons.append("higher-than-average export volume")

    if profile.get("num_trade_events", 0) > means.get("num_trade_events", 0):
        reasons.append("frequent export transactions")

    if profile.get("source_risk", 0) > means.get("source_risk", 0):
        reasons.append("predominantly wild-sourced specimens")

    if profile.get("live_trade_ratio", 0) > means.get("live_trade_ratio", 0):
        reasons.append("significant live animal trade")

    if profile.get("appendix_risk", 0) >= 2:
        reasons.append("higher CITES protection status")

    if not reasons:
        return "Risk is moderate due to average trade behavior."

    return "Risk is elevated due to " + ", ".join(reasons) + "."

# --- 5. API ROUTES ---

@app.route("/get_animal_data", methods=["GET"])
def get_animal_data():
    taxon = request.args.get("taxon")
    if not taxon:
        return jsonify({"error": "No taxon provided"}), 400

    taxon_clean = taxon.strip().lower()

    # Prediction lookup
    prediction = db.predictions.find_one(
        {"Taxon": {"$regex": f"^{taxon}$", "$options": "i"}},
        {"_id": 0}
    )

    if not prediction:
        return jsonify({"error": "Species not found"}), 404

    # Species facts
    facts = SPECIES_FACTS.get(taxon_clean)
    why_text = (
        f"This species {facts['poaching_reason']} "
        if facts
        else "Demand-driven international trade pressure detected. "
    )

    # Feature data for heatmap
    features = list(db.features.find(
        {"Taxon": {"$regex": f"^{taxon}$", "$options": "i"}},
        {"_id": 0}
    ))

    # Country-specific risk explanation
    likely_country = prediction.get("likely_poaching_country")
    specific_profile = next(
        (f for f in features if f.get("Exporter") == likely_country),
        None
    )

    how_text = explain_risk(specific_profile, GLOBAL_MEANS)

    return jsonify({
        "basic_info": prediction,
        "heatmap_data": features,
        "risk_explanation": why_text + how_text
    })

@app.route("/get_species_facts", methods=["GET"])
def get_species_facts():
    taxon = request.args.get("taxon")
    if not taxon:
        return jsonify({"error": "No taxon provided"}), 400

    facts = SPECIES_FACTS.get(taxon.strip().lower())
    if not facts:
        return jsonify({"error": "Species facts not found"}), 404

    return jsonify(facts)

@app.route("/get_comparison_data", methods=["GET"])
def get_comparison_data():
    try:
        # CSV is in the same folder as this file
        df = pd.read_csv("5_Species_Summary.csv")
        return jsonify(df.to_dict(orient="records"))
    except FileNotFoundError:
        return jsonify({"error": "Comparison data CSV missing."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 6. RUN SERVER ---
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
