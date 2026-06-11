"""
Patient Clustering Script
--------------------------
MY OWN FORMAT - not platform compliant.

Input  : measurement CSV file (OMOP format)
Output : clustered_patients.csv with PCA coords + cluster labels + clinical scores
         (this file is ready to upload directly into Apache Superset for scatter plot)

Usage:
    python clustering.py measurement.csv clustered_patients.csv
"""

import sys
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA


def cluster_patients(input_csv, output_csv, n_clusters=3):
    # ── Load ──────────────────────────────────────────────────────────────
    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} rows, {df['person_id'].nunique()} patients")

    # ── Pivot to patient-level feature matrix ─────────────────────────────
    pivot = df.pivot_table(
        index='person_id',
        columns='measurement_source_value',
        values='value_as_number',
        aggfunc='mean'
    ).reset_index()

    person_ids = pivot['person_id']
    X = pivot.drop(columns=['person_id'])

    # ── Impute missing values + standardize ───────────────────────────────
    X_imputed = SimpleImputer(strategy='mean').fit_transform(X)
    X_scaled  = StandardScaler().fit_transform(X_imputed)

    # ── KMeans clustering ─────────────────────────────────────────────────
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X_scaled)

    # ── PCA to 2D for scatter plot ────────────────────────────────────────
    pca    = PCA(n_components=2)
    X_pca  = pca.fit_transform(X_scaled)
    print(f"PCA variance explained: PC1={pca.explained_variance_ratio_[0]*100:.1f}%  PC2={pca.explained_variance_ratio_[1]*100:.1f}%")

    # ── Clinical summary scores per patient ───────────────────────────────
    ham_d_cols = [c for c in pivot.columns if 'ham_d' in str(c)]
    psqi_cols  = [c for c in pivot.columns if 'psqi'  in str(c) and 'cumulative' not in str(c)]
    cdr_cols   = [c for c in pivot.columns if 'cdr'   in str(c)]

    ham_d_total = pivot[ham_d_cols].sum(axis=1).round(2).values
    psqi_total  = pivot[psqi_cols].sum(axis=1).round(2).values
    cdr_score   = pivot[cdr_cols].mean(axis=1).round(2).values

    # ── Assign human-readable cluster names based on HAM-D severity ───────
    cluster_means = {}
    for c in range(n_clusters):
        mask = labels == c
        cluster_means[c] = ham_d_total[mask].mean()

    sorted_clusters = sorted(cluster_means, key=cluster_means.get)
    name_map = {}
    severity_names = ['Low Severity', 'Moderate Severity', 'High Severity']
    for i, c in enumerate(sorted_clusters):
        name_map[c] = severity_names[i] if n_clusters == 3 else f'Cluster {i}'

    # ── Build output dataframe ────────────────────────────────────────────
    result = pd.DataFrame({
        'person_id':        person_ids.values,
        'pca_x':            X_pca[:, 0].round(4),
        'pca_y':            X_pca[:, 1].round(4),
        'cluster':          labels,
        'cluster_label':    [name_map[l] for l in labels],
        'ham_d_total':      ham_d_total,
        'psqi_total':       psqi_total,
        'cdr_score':        cdr_score,
        'num_measurements': df.groupby('person_id')['measurement_id'].count().reindex(person_ids.values).values,
    })

    result.to_csv(output_csv, index=False)
    print(f"\nSaved {len(result)} patients to {output_csv}")
    print("\nCluster summary:")
    print(result.groupby('cluster_label')[['ham_d_total','psqi_total','cdr_score']].mean().round(2))


if __name__ == '__main__':
    input_path  = sys.argv[1] if len(sys.argv) > 1 else 'measurement.csv'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'clustered_patients.csv'
    cluster_patients(input_path, output_path)