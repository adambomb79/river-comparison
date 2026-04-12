name: Update comparison JSON

on:
  workflow_dispatch:
  schedule:
    - cron: "15 10 * * *"

jobs:
  build:
    runs-on: ubuntu-latest

    permissions:
      contents: write

    steps:
      - name: Check out repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Run generator
        run: python build_comparison.py

      - name: Commit updated comparison.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add comparison.json
          git diff --cached --quiet || git commit -m "Update comparison.json"
          git push
