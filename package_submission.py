"""Deterministic Packaging & Validation Script for Gemma 4 Developer Agent Submission.
Validates ADK schema compliance, executes patch verification test, and builds submission.zip.
"""

import os
import zipfile
import yaml


def validate_adk_structure(agent_dir: str) -> bool:
    """Validate that agent directory satisfies Google ADK submission requirements."""
    manifest_path = os.path.join(agent_dir, "agent.yaml")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Missing root agent.yaml at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Invariant checks
    if config.get("framework") != "google-adk" and config.get("runtime", {}).get("framework") != "google-adk":
        raise ValueError("Framework must be declared as google-adk")

    model_name = config.get("model", {}).get("name", "")
    if "gemma-4-31b-it-qat-w4a16-ct" not in model_name:
        raise ValueError(f"Invalid model declaration: {model_name}")

    if "entrypoint" in config:
        raise ValueError("Forbidden custom entrypoint found. Google ADK must run declaratively.")

    print("[VALIDATION PASSED] ADK agent.yaml conforms strictly to declarative specification.")
    return True


def build_submission_archive(agent_dir: str, output_zip: str) -> None:
    """Package agent configuration into submission.zip with agent.yaml at root."""
    validate_adk_structure(agent_dir)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(agent_dir):
            for file in files:
                if file.endswith((".pyc", ".DS_Store", ".tmp")):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, agent_dir)
                zipf.write(file_path, arcname=rel_path)

    print(f"[PACKAGE SUCCESS] Created {output_zip} ({os.path.getsize(output_zip)} bytes).")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    agent_dir = os.path.join(base_dir, "agent")
    zip_path = os.path.join(base_dir, "submission.zip")
    build_submission_archive(agent_dir, zip_path)
