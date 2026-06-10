"""
Patient Clustering Script
--------------------------
My custom clustering script.
- Input  : a CSV file path (passed as command-line argument)
- Output : a CSV file with a 'cluster' column added

This is NOT platform compliant. It reads/writes plain local CSV files.
"""

import sys
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer


def cluster_patients(input_csv: str, output_csv: str, n_clusters: int = 3):
    # Load CSV
    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} rows")

    # Pivot: one row per patient, one column per measurement type
    pivot = df.pivot_table(
        index="person_id",
        columns="measurement_source_value",
        values="value_as_number",
        aggfunc="mean"
    ).reset_index()

    person_ids = pivot["person_id"]
    X = pivot.drop(columns=["person_id"])

    # Impute missing + scale
    X_imputed = SimpleImputer(strategy="mean").fit_transform(X)
    X_scaled  = StandardScaler().fit_transform(X_imputed)

    # KMeans
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X_scaled)

    cluster_map = pd.DataFrame({"person_id": person_ids.values, "cluster": labels})
    result = df.merge(cluster_map, on="person_id", how="left")
    result.to_csv(output_csv, index=False)
    print(f"Saved to {output_csv}")
    for i in range(n_clusters):
        print(f"  Cluster {i}: {(labels == i).sum()} patients")


if __name__ == "__main__":
    input_path  = sys.argv[1] if len(sys.argv) > 1 else "measurement.csv"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "output.csv"
    cluster_patients(input_path, output_path, n_clusters=3)