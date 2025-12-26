import pandas as pd

# ---------------------------
# Load precomputed data
# ---------------------------
final_output = pd.read_csv("Final_Output.csv")
feature_df = pd.read_csv("Feature_Matrix.csv")

# ---------------------------
# Helper: explain risk
# ---------------------------
def explain_risk(taxon, country):
    profile = feature_df[
        (feature_df['Taxon'] == taxon) &
        (feature_df['Exporter'] == country)
    ]

    if profile.empty:
        return "No detailed trade profile available."

    profile = profile.iloc[0]
    means = feature_df.mean(numeric_only=True)

    reasons = []

    if profile['export_qty_log'] > means['export_qty_log']:
        reasons.append("higher-than-average export volume")

    if profile['num_trade_events'] > means['num_trade_events']:
        reasons.append("frequent export transactions")

    if profile['source_risk'] > means['source_risk']:
        reasons.append("predominantly wild-sourced specimens")

    if profile['live_trade_ratio'] > means['live_trade_ratio']:
        reasons.append("significant live animal trade")

    if profile['appendix_risk'] >= 2:
        reasons.append("higher CITES protection status")

    if not reasons:
        return "Risk is moderate due to average trade behavior."

    return (
        "Risk is elevated due to "
        + ", ".join(reasons)
        + "."
    )

# ---------------------------
# Main CLI logic
# ---------------------------
def main():
    print("\n--- Wildlife Poaching Risk Estimation System ---\n")

    taxon = input("Enter Species (Taxon name): ").strip()

    match = final_output[final_output['Taxon'] == taxon]

    if match.empty:
        print("\n❌ Species not found in dataset.")
        return

    row = match.iloc[0]

    country = row['likely_poaching_country']
    risk = row['poaching_risk_score']

    explanation = explain_risk(taxon, country)

    print("\n--- Prediction Result ---")
    print(f"Species                : {row['Taxon']}")
    print(f"Order                  : {row['Order']}")
    print(f"Family                 : {row['Family']}")
    print(f"Genus                  : {row['Genus']}")
    print(f"Likely Poaching Country: {country}")
    print(f"Poaching Risk Score    : {risk:.3f}")
    print("\nExplanation:")
    print(f"- {explanation}")

    print("\n--- Done ---\n")

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    main()
